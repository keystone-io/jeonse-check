from datetime import date, timedelta

from clients import _normalize_rtms, _parse_bld, normalize_jibun
from diagnosis import Target, diagnose, fmt_money

TODAY = date(2026, 11, 13)


def d(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def rec(days_ago, area, jibun="123-4", umd="역삼동", **kw):
    return {
        "date": d(days_ago), "ym": d(days_ago)[:7].replace("-", ""), "name": "테스트빌라", "area": area,
        "floor": "3", "jibun": jibun, "umd": umd, "umd_cd": "", "build_year": 2015, **kw,
    }


def target(**kw):
    base = dict(b_code="1168010100", main_no="123", sub_no="4", dong="역삼동", sido="서울특별시",
                house_type="rh", deposit=20000)
    base.update(kw)
    return Target(**base)


def get(result, cid):
    return next(c for c in result["checks"] if c["id"] == cid)


TRADES = [
    rec(30, 59.9, price=30000), rec(90, 59.8, price=29000), rec(200, 59.9, price=31000),
    rec(500, 59.9, price=32000), rec(600, 59.9, price=33000), rec(60, 84.9, price=45000),
    rec(40, 60.0, jibun="200", price=10000),  # 다른 건물
]
RENTS = [
    rec(20, 59.9, deposit=21000, monthly=0), rec(100, 59.9, deposit=20000, monthly=0),
    rec(50, 59.9, deposit=5000, monthly=80),  # 월세는 제외
]
TITLES = [{"mainPurpsCdNm": "공동주택", "etcPurps": "다세대주택", "useAprDay": "20150310", "bldNm": "테스트빌라"}]


def test_helpers():
    assert normalize_jibun("0123-0004") == "123-4"
    assert normalize_jibun("123-0") == "123"
    assert fmt_money(32500) == "3억 2,500만원"
    assert fmt_money(30000) == "3억원"
    assert fmt_money(800) == "800만원"


def test_auto_area_and_ratio():
    r = diagnose(target(), TRADES, RENTS, TITLES, [], [], today=TODAY)
    assert abs(r["area"]["selected"] - 59.9) < 0.2 and r["area"]["source"] == "auto"
    # 최근 1년 같은 건물 59㎡: 30000, 29000, 31000 → 중앙값 30000 → 20000/30000 = 67%
    assert get(r, "ratio")["value"] == "67%" and get(r, "ratio")["status"] == "good"
    assert get(r, "market")["status"] == "good"  # 20000 vs 중앙값 20500
    assert get(r, "building")["status"] == "good"
    assert get(r, "guarantee")["status"] == "unknown"


def test_senior_debt_and_guarantee():
    r = diagnose(target(senior_debt=6000, official_price=15000), TRADES, RENTS, TITLES, [], [], today=TODAY)
    assert get(r, "ratio")["value"] == "87%" and get(r, "ratio")["status"] == "danger"  # 26000/30000
    assert get(r, "guarantee")["status"] == "danger"  # 26000 > 15000*1.26
    assert r["overall"]["status"] == "danger"


def test_guarantee_ok():
    r = diagnose(target(official_price=17000), TRADES, RENTS, TITLES, [], [], today=TODAY)
    assert get(r, "guarantee")["status"] == "good"  # 20000 <= 21420


def test_guarantee_limit_non_capital():
    r = diagnose(target(sido="부산광역시", deposit=60000), TRADES, RENTS, TITLES, [], [], today=TODAY)
    assert get(r, "guarantee")["value"] == "한도 초과"


def test_trend_down():
    r = diagnose(target(), TRADES, RENTS, TITLES, [], [], today=TODAY)
    # 최근 6개월 30000, 29000 vs 1~2년 전 32000, 33000 → 약 -9%
    assert get(r, "trend")["status"] == "caution"


def test_neighborhood_fallback_and_cheap_market():
    other = [rec(30 + i, 60.0, jibun=str(300 + i), price=28000 + i * 100) for i in range(4)]
    rents = [rec(30 + i, 60.0, jibun=str(300 + i), deposit=25000, monthly=0) for i in range(4)]
    r = diagnose(target(area=59.5, deposit=15000), other, rents, [], [], [], today=TODAY)
    assert r["estimates"]["sale"]["scope"] == "nearby"
    assert get(r, "market")["status"] == "caution" and "싸요" in get(r, "market")["summary"]
    assert get(r, "building")["status"] == "unknown"


def test_commercial_building_is_danger():
    titles = [{"mainPurpsCdNm": "제2종근린생활시설", "useAprDay": "20200101"}]
    r = diagnose(target(), TRADES, RENTS, titles, [], [], today=TODAY)
    assert get(r, "building")["status"] == "danger"


def test_no_data():
    r = diagnose(target(), [], [], [], [], [], today=TODAY)
    assert r["overall"]["status"] == "unknown"


def test_normalize_rtms_and_cancelled_deal():
    raw = {"dealYear": "2026", "dealMonth": "10", "dealDay": "5", "dealAmount": " 32,500", "excluUseAr": "59.94",
           "jibun": "123-4", "umdNm": "역삼동", "mhouseNm": "테스트빌라", "buildYear": "2015", "cdealType": ""}
    r = _normalize_rtms(raw, "trade", "mhouseNm")
    assert r["price"] == 32500 and r["date"] == "2026-10-05" and r["name"] == "테스트빌라"
    assert _normalize_rtms({**raw, "cdealType": "O"}, "trade", "mhouseNm") is None
    rent = _normalize_rtms({**raw, "deposit": "20,000", "monthlyRent": "0"}, "rent", "mhouseNm")
    assert rent["deposit"] == 20000 and rent["monthly"] == 0


def test_parse_bld_json_variants():
    one = '{"response":{"header":{"resultCode":"00"},"body":{"items":{"item":{"bldNm":"A"}},"totalCount":"1"}}}'
    assert _parse_bld(one) == [{"bldNm": "A"}]
    empty = '{"response":{"header":{"resultCode":"00"},"body":{"items":"","totalCount":"0"}}}'
    assert _parse_bld(empty) == []
