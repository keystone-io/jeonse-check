"""외부 API 호출 (카카오 로컬, 공공데이터포털 실거래가·건축물대장).

모든 응답은 프론트에 필요한 필드만 남겨 정규화한다.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from cache import Cache

KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

RTMS_BASE = "https://apis.data.go.kr/1613000"
BLD_BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"

# 주택 유형별 실거래가 서비스 이름과 단지(건물)명 필드
HOUSE_TYPES = {
    "apt": {"label": "아파트", "trade": "RTMSDataSvcAptTrade", "rent": "RTMSDataSvcAptRent", "name": "aptNm"},
    "rh": {"label": "연립·다세대(빌라)", "trade": "RTMSDataSvcRHTrade", "rent": "RTMSDataSvcRHRent", "name": "mhouseNm"},
    "offi": {"label": "오피스텔", "trade": "RTMSDataSvcOffiTrade", "rent": "RTMSDataSvcOffiRent", "name": "offiNm"},
}

# 공공데이터포털 인증 오류 코드 → 한국어 안내
AUTH_ERRORS = {
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR": "공공데이터포털 인증키가 등록되지 않았습니다. 키 값(Decoding 키)과 해당 API 활용신청 여부를 확인하세요. 신청 직후라면 1~2시간 뒤 다시 시도하세요.",
    "SERVICE_ACCESS_DENIED_ERROR": "이 API에 대한 활용신청이 되어 있지 않습니다. 공공데이터포털에서 활용신청을 해주세요.",
    "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR": "공공데이터포털 일일 호출 한도를 초과했습니다. 내일 다시 시도하세요.",
    "DEADLINE_HAS_EXPIRED_ERROR": "공공데이터포털 활용 기간이 만료되었습니다. 연장 신청을 해주세요.",
}


class UpstreamError(Exception):
    """외부 API 오류 (사용자에게 보여줄 한국어 메시지 포함)."""


class MissingKeyError(Exception):
    """.env 에 키가 없을 때."""


def _num(value) -> float | None:
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_jibun(value: str | None) -> str:
    """'0123-0004', '123-4', '123' 등을 '123-4' / '123' 형태로 통일."""
    if not value:
        return ""
    parts = str(value).strip().split("-")
    try:
        main = int(parts[0])
    except ValueError:
        return str(value).strip()
    sub = 0
    if len(parts) > 1:
        try:
            sub = int(parts[1])
        except ValueError:
            sub = 0
    return f"{main}-{sub}" if sub else str(main)


def month_list(months: int, today: date | None = None) -> list[str]:
    """오늘 포함 최근 n개월의 'YYYYMM' 목록 (최신순)."""
    today = today or date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(months):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


# ---------------------------------------------------------------- 카카오


class KakaoClient:
    def __init__(self, http: httpx.AsyncClient, api_key: str, cache: Cache) -> None:
        self.http = http
        self.api_key = api_key
        self.cache = cache

    def _headers(self) -> dict:
        if not self.api_key:
            raise MissingKeyError("KAKAO_REST_API_KEY 가 설정되지 않았습니다. backend/.env 에 카카오 REST API 키를 입력하세요.")
        return {"Authorization": f"KakaoAK {self.api_key}"}

    async def _get(self, url: str, params: dict) -> dict:
        resp = await self.http.get(url, params=params, headers=self._headers())
        if resp.status_code in (401, 403):
            raise UpstreamError(
                "카카오 API 인증에 실패했습니다. REST API 키가 맞는지, 앱에서 카카오맵 사용 설정이 ON 인지 확인하세요."
            )
        if resp.status_code == 429:
            raise UpstreamError("카카오 API 일일 무료 사용량을 초과했습니다. 내일 다시 시도하세요.")
        if resp.status_code != 200:
            raise UpstreamError(f"카카오 주소 검색 오류 (HTTP {resp.status_code})")
        return resp.json()

    @staticmethod
    def _to_result(doc: dict) -> dict | None:
        addr = doc.get("address") or {}
        road = doc.get("road_address") or {}
        b_code = addr.get("b_code") or ""
        main_no = addr.get("main_address_no") or ""
        if len(b_code) != 10 or not main_no:
            return None  # 동·구 단위 결과처럼 지번이 없는 것은 진단할 수 없음
        return {
            "id": f"{b_code}-{addr.get('mountain_yn', 'N')}-{main_no}-{addr.get('sub_address_no') or '0'}",
            "jibun_address": addr.get("address_name") or doc.get("address_name"),
            "road_address": road.get("address_name") or "",
            "building_name": road.get("building_name") or "",
            "b_code": b_code,
            "main_no": main_no,
            "sub_no": addr.get("sub_address_no") or "",
            "mountain": addr.get("mountain_yn") == "Y",
            "sido": addr.get("region_1depth_name") or "",
            "sigungu": addr.get("region_2depth_name") or "",
            "dong": addr.get("region_3depth_name") or "",
            "x": _num(doc.get("x")),
            "y": _num(doc.get("y")),
        }

    async def search(self, query: str) -> list[dict]:
        query = query.strip()
        key = f"kakao:search:{query}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        data = await self._get(KAKAO_ADDRESS_URL, {"query": query, "size": 10})
        results = [r for r in (self._to_result(d) for d in data.get("documents", [])) if r]

        # 주소로 못 찾으면 장소(단지명) 검색 → 그 지번 주소로 다시 주소 검색
        if not results:
            kw = await self._get(KAKAO_KEYWORD_URL, {"query": query, "size": 5})
            seen = set()
            for place in kw.get("documents", []):
                addr_name = place.get("address_name")
                if not addr_name or addr_name in seen:
                    continue
                seen.add(addr_name)
                sub = await self._get(KAKAO_ADDRESS_URL, {"query": addr_name, "size": 1})
                for d in sub.get("documents", []):
                    r = self._to_result(d)
                    if r:
                        if not r["building_name"]:
                            r["building_name"] = place.get("place_name") or ""
                        results.append(r)
                        break

        # 중복 제거
        uniq, ids = [], set()
        for r in results:
            if r["id"] not in ids:
                ids.add(r["id"])
                uniq.append(r)

        self.cache.set(key, uniq, 7 * 24 * 3600)
        return uniq


# ---------------------------------------------------------------- 공공데이터포털


def _check_auth_error(text: str) -> None:
    if "OpenAPI_ServiceResponse" in text or "returnAuthMsg" in text:
        for code, msg in AUTH_ERRORS.items():
            if code in text:
                raise UpstreamError(msg)
        raise UpstreamError("공공데이터포털 API 오류가 발생했습니다.")


class DataGoKrClient:
    def __init__(self, http: httpx.AsyncClient, api_key: str, cache: Cache, concurrency: int = 6) -> None:
        self.http = http
        self.api_key = api_key
        self.cache = cache
        self.sem = asyncio.Semaphore(concurrency)

    def _require_key(self) -> None:
        if not self.api_key:
            raise MissingKeyError(
                "DATA_GO_KR_API_KEY 가 설정되지 않았습니다. backend/.env 에 공공데이터포털 인증키(Decoding)를 입력하세요."
            )

    async def _get_text(self, url: str, params: dict) -> str:
        self._require_key()
        params = {"serviceKey": self.api_key, **params}
        async with self.sem:
            for attempt in range(3):
                try:
                    resp = await self.http.get(url, params=params)
                    break
                except httpx.TransportError:
                    if attempt == 2:
                        raise UpstreamError("공공데이터포털 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.")
                    await asyncio.sleep(0.5 * (attempt + 1))
        text = resp.text
        _check_auth_error(text)
        if resp.status_code in (401, 403):
            raise UpstreamError(AUTH_ERRORS["SERVICE_KEY_IS_NOT_REGISTERED_ERROR"])
        if resp.status_code != 200:
            raise UpstreamError(f"공공데이터포털 응답 오류 (HTTP {resp.status_code})")
        return text

    # ---- 실거래가 -------------------------------------------------------

    async def _rtms_month(self, service: str, lawd_cd: str, ym: str) -> list[dict]:
        key = f"rtms:{service}:{lawd_cd}:{ym}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        url = f"{RTMS_BASE}/{service}/get{service}"
        items: list[dict] = []
        page = 1
        while True:
            text = await self._get_text(
                url, {"LAWD_CD": lawd_cd, "DEAL_YMD": ym, "pageNo": page, "numOfRows": 1000}
            )
            try:
                root = ET.fromstring(text)
            except ET.ParseError:
                raise UpstreamError("공공데이터포털 응답을 해석하지 못했습니다.")
            code = (root.findtext(".//resultCode") or "").strip()
            if code and code not in ("00", "000"):
                msg = (root.findtext(".//resultMsg") or "").strip()
                raise UpstreamError(f"실거래가 API 오류: {msg or code}")
            for it in root.iter("item"):
                items.append({child.tag: (child.text or "").strip() for child in it})
            total = int(_num(root.findtext(".//totalCount")) or 0)
            if page * 1000 >= total:
                break
            page += 1

        # 지난 달 데이터는 거의 바뀌지 않으므로 오래 보관, 최근 2개월은 신고가 계속 들어오므로 짧게
        recent = month_list(2)
        ttl = 12 * 3600 if ym in recent else 7 * 24 * 3600
        self.cache.set(key, items, ttl)
        return items

    async def rtms(self, house_type: str, kind: str, lawd_cd: str, months: int) -> tuple[list[dict], list[str]]:
        """kind: 'trade' | 'rent'. 정규화된 거래 목록과 경고 목록을 돌려준다."""
        spec = HOUSE_TYPES[house_type]
        service = spec[kind]
        yms = month_list(months)
        results = await asyncio.gather(
            *(self._rtms_month(service, lawd_cd, ym) for ym in yms), return_exceptions=True
        )
        records: list[dict] = []
        warnings: list[str] = []
        for ym, res in zip(yms, results):
            if isinstance(res, MissingKeyError):
                raise res
            if isinstance(res, Exception):
                msg = str(res) if isinstance(res, UpstreamError) else "알 수 없는 오류"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            for raw in res:
                rec = _normalize_rtms(raw, kind, spec["name"])
                if rec:
                    records.append(rec)
        # 모든 달이 실패하면 오류로 처리
        if all(isinstance(r, Exception) for r in results):
            raise UpstreamError(warnings[0] if warnings else "실거래가 데이터를 가져오지 못했습니다.")
        return records, warnings

    # ---- 건축물대장 -------------------------------------------------------

    async def _bld(self, operation: str, b_code: str, main_no: str, sub_no: str, mountain: bool) -> list[dict]:
        params = {
            "sigunguCd": b_code[:5],
            "bjdongCd": b_code[5:],
            "platGbCd": "1" if mountain else "0",
            "bun": str(main_no).zfill(4),
            "ji": str(sub_no or "0").zfill(4),
            "numOfRows": 100,
            "pageNo": 1,
            "_type": "json",
        }
        key = "bld:" + operation + ":" + ":".join(str(params[k]) for k in ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji"))
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # 건축물대장 API 는 가끔 일시적인 오류 응답을 주므로 한 번 더 시도한다 (인증 오류는 제외)
        for attempt in range(2):
            try:
                text = await self._get_text(f"{BLD_BASE}/{operation}", params)
                items = _parse_bld(text)
                break
            except UpstreamError as e:
                if attempt == 1 or any(msg == str(e) for msg in AUTH_ERRORS.values()):
                    raise
                await asyncio.sleep(0.7)
        self.cache.set(key, items, 7 * 24 * 3600)
        return items

    async def building_title(self, b_code, main_no, sub_no, mountain) -> list[dict]:
        return await self._bld("getBrTitleInfo", b_code, main_no, sub_no, mountain)

    async def building_recap(self, b_code, main_no, sub_no, mountain) -> list[dict]:
        return await self._bld("getBrRecapTitleInfo", b_code, main_no, sub_no, mountain)

    async def house_price(self, b_code, main_no, sub_no, mountain) -> list[dict]:
        return await self._bld("getBrHsprcInfo", b_code, main_no, sub_no, mountain)


def _parse_bld(text: str) -> list[dict]:
    import json

    text = text.strip()
    if text.startswith("{"):
        data = json.loads(text)
        resp = data.get("response", data)
        header = resp.get("header", {})
        code = str(header.get("resultCode", "00"))
        if code not in ("00", "000"):
            raise UpstreamError(f"건축물대장 API 오류: {header.get('resultMsg', code)}")
        items = (resp.get("body") or {}).get("items") or {}
        if not isinstance(items, dict):
            return []
        item = items.get("item") or []
        if isinstance(item, dict):
            item = [item]
        return [{k: ("" if v is None else str(v).strip()) for k, v in it.items()} for it in item]

    # JSON 요청이 무시되고 XML 로 오는 경우
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise UpstreamError("건축물대장 응답을 해석하지 못했습니다.")
    code = (root.findtext(".//resultCode") or "00").strip()
    if code not in ("00", "000"):
        raise UpstreamError(f"건축물대장 API 오류: {(root.findtext('.//resultMsg') or code).strip()}")
    return [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]


def _normalize_rtms(raw: dict, kind: str, name_field: str) -> dict | None:
    year = raw.get("dealYear") or ""
    month = raw.get("dealMonth") or ""
    day = raw.get("dealDay") or "1"
    try:
        d = date(int(year), int(month), int(day or 1))
    except ValueError:
        return None
    area = _num(raw.get("excluUseAr"))
    rec = {
        "date": d.isoformat(),
        "ym": f"{d.year:04d}{d.month:02d}",
        "name": raw.get(name_field) or "",
        "area": area,
        "floor": raw.get("floor") or "",
        "jibun": normalize_jibun(raw.get("jibun")),
        "umd": (raw.get("umdNm") or "").strip(),
        "umd_cd": (raw.get("umdCd") or "").strip(),
        "build_year": int(_num(raw.get("buildYear")) or 0) or None,
    }
    if kind == "trade":
        if (raw.get("cdealType") or "").strip().upper() == "O":
            return None  # 해제(취소)된 거래 제외
        price = _num(raw.get("dealAmount"))
        if not price:
            return None
        rec["price"] = price
    else:
        deposit = _num(raw.get("deposit"))
        if not deposit:
            return None
        rec["deposit"] = deposit
        rec["monthly"] = _num(raw.get("monthlyRent")) or 0
    return rec
