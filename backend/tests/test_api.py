import pytest
from fastapi.testclient import TestClient

import main
from clients import DataGoKrClient, KakaoClient

BODY = {
    "b_code": "1168010100", "main_no": "123", "sub_no": "4", "sido": "서울특별시", "dong": "역삼동",
    "house_type": "rh", "deposit": 20000,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "dummy")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "dummy")
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["keys"] == {"data_go_kr": True, "kakao": True}


def test_missing_key_message(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "")
    with TestClient(main.app) as c:
        r = c.post("/api/diagnose", json=BODY)
    assert r.status_code == 500 and "DATA_GO_KR_API_KEY" in r.json()["detail"]


def test_validation(client):
    assert client.post("/api/diagnose", json={**BODY, "b_code": "abc"}).status_code == 422
    assert client.post("/api/diagnose", json={**BODY, "deposit": -1}).status_code == 422


def test_diagnose_with_mocked_upstream(client, monkeypatch):
    async def fake_rtms(self, house_type, kind, lawd, months):
        assert lawd == "11680"
        if kind == "trade":
            return [{"date": "2026-10-01", "ym": "202610", "name": "빌라", "area": 59.9, "floor": "2",
                     "jibun": "123-4", "umd": "역삼동", "umd_cd": "10100", "build_year": 2015, "price": 30000}], []
        return [], ["일부 오류"]

    async def fake_title(self, *a):
        return [{"mainPurpsCdNm": "공동주택", "useAprDay": "20150101"}]

    async def empty(self, *a):
        return []

    monkeypatch.setattr(DataGoKrClient, "rtms", fake_rtms)
    monkeypatch.setattr(DataGoKrClient, "building_title", fake_title)
    monkeypatch.setattr(DataGoKrClient, "building_recap", empty)
    monkeypatch.setattr(DataGoKrClient, "house_price", empty)
    r = client.post("/api/diagnose", json=BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["house_type"]["label"].startswith("연립")
    assert {c["id"] for c in data["checks"]} == {"ratio", "market", "guarantee", "building", "trend"}
    assert any("일부 오류" in w for w in data["warnings"])


def test_address_mocked(client, monkeypatch):
    async def fake_search(self, q):
        return [{"id": "x", "jibun_address": q}]

    monkeypatch.setattr(KakaoClient, "search", fake_search)
    r = client.get("/api/address", params={"q": "역삼동 123"})
    assert r.status_code == 200 and r.json()["results"][0]["jibun_address"] == "역삼동 123"
