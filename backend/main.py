"""jeonse-check 백엔드 — 외부 API 프록시 + 전세 안전 진단."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cache import Cache
from clients import HOUSE_TYPES, DataGoKrClient, KakaoClient, MissingKeyError, UpstreamError
from diagnosis import Target, diagnose

load_dotenv(Path(__file__).resolve().parent / ".env")

MONTHS = int(os.getenv("RTMS_MONTHS", "24"))  # 조회할 실거래 기간(개월)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0))
    app.state.cache = Cache()
    app.state.cache.purge_expired()
    yield
    await app.state.http.aclose()


app = FastAPI(title="jeonse-check API", lifespan=lifespan)


def kakao(request: Request) -> KakaoClient:
    return KakaoClient(request.app.state.http, os.getenv("KAKAO_REST_API_KEY", "").strip(), request.app.state.cache)


def datagokr(request: Request) -> DataGoKrClient:
    return DataGoKrClient(request.app.state.http, os.getenv("DATA_GO_KR_API_KEY", "").strip(), request.app.state.cache)


@app.exception_handler(MissingKeyError)
async def _missing_key(_: Request, exc: MissingKeyError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(UpstreamError)
async def _upstream(_: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "keys": {
            "data_go_kr": bool(os.getenv("DATA_GO_KR_API_KEY", "").strip()),
            "kakao": bool(os.getenv("KAKAO_REST_API_KEY", "").strip()),
        },
    }


@app.get("/api/address")
async def address(request: Request, q: str = Query(..., min_length=2, max_length=100)):
    return {"results": await kakao(request).search(q)}


class DiagnoseIn(BaseModel):
    b_code: str = Field(..., pattern=r"^\d{10}$")
    main_no: str = Field(..., pattern=r"^\d{1,4}$")
    sub_no: str = Field("", pattern=r"^\d{0,4}$")
    mountain: bool = False
    sido: str = ""
    dong: str = ""
    building_name: str = ""
    house_type: Literal["apt", "rh", "offi"]
    deposit: float = Field(..., gt=0, le=1_000_000, description="보증금(만원)")
    area: float | None = Field(None, gt=0, le=1000, description="전용면적(㎡)")
    senior_debt: float = Field(0, ge=0, le=1_000_000, description="선순위 채권(만원)")
    official_price: float | None = Field(None, gt=0, le=1_000_000, description="공시가격(만원)")


@app.post("/api/diagnose")
async def diagnose_api(request: Request, body: DiagnoseIn):
    client = datagokr(request)
    client._require_key()
    lawd = body.b_code[:5]
    args = (body.b_code, body.main_no, body.sub_no, body.mountain)

    async def safe(coro, label):
        try:
            return await coro, None
        except MissingKeyError:
            raise
        except UpstreamError as e:
            return None, f"{label}: {e}"
        except Exception:
            return None, f"{label}: 데이터를 가져오지 못했습니다."

    # 건축물대장 '주택가격'(getBrHsprcInfo)은 공동주택의 경우 호별 이력이 수만 건이고 동·호 정보가 없어
    # 해당 세대를 특정할 수 없으므로 사용하지 않는다. 공시가격은 사용자 입력값만 쓴다.
    (trade_res, w1), (rent_res, w2), (titles, w3), (recaps, _w4) = await asyncio.gather(
        safe(client.rtms(body.house_type, "trade", lawd, MONTHS), "매매 실거래가"),
        safe(client.rtms(body.house_type, "rent", lawd, MONTHS), "전월세 실거래가"),
        safe(client.building_title(*args), "건축물대장"),
        safe(client.building_recap(*args), "건축물대장 총괄표제부"),
    )
    prices: list[dict] = []
    warnings = [w for w in (w1, w2, w3) if w]  # 총괄표제부는 없는 건물이 많아 경고 생략
    trades, tw = trade_res or ([], [])
    rents, rw = rent_res or ([], [])
    for w in tw + rw:
        msg = f"일부 기간 실거래가 누락: {w}"
        if msg not in warnings:
            warnings.append(msg)

    target = Target(
        b_code=body.b_code,
        main_no=body.main_no,
        sub_no=body.sub_no,
        dong=body.dong,
        sido=body.sido,
        house_type=body.house_type,
        deposit=body.deposit,
        area=body.area,
        senior_debt=body.senior_debt,
        official_price=body.official_price,
        building_name=body.building_name,
    )
    failed = frozenset(k for k, res in (("trade", trade_res), ("rent", rent_res)) if res is None)
    result = diagnose(target, trades, rents, titles or [], recaps or [], prices or [], failed=failed)
    result["house_type"] = {"code": body.house_type, "label": HOUSE_TYPES[body.house_type]["label"]}
    result["months"] = MONTHS
    result["warnings"] = warnings
    return result
