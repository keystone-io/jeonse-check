"""전세 안전 진단 계산 (외부 호출 없음 — 정규화된 거래 데이터만 받아 판단).

금액 단위는 모두 '만원'.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from clients import normalize_jibun

# ---- 판단 기준 (필요 시 여기만 수정) ---------------------------------------
JEONSE_RATIO_GOOD = 70  # 전세가율 70% 이하 → 양호
JEONSE_RATIO_CAUTION = 80  # 80% 이하 → 주의, 초과 → 위험
MARKET_LOW = 0.85  # 주변 전세 시세의 85% 미만이면 "너무 싸다" 주의
MARKET_HIGH = 1.1  # 110% 초과면 "비싸다" 주의
HUG_OFFICIAL_RATE = 1.26  # 공시가격 × 140% × 전세가율 90% (HUG 기준, 변경 가능성 있음)
HUG_LIMIT_CAPITAL = 70000  # 수도권 보증금 한도 7억
HUG_LIMIT_OTHER = 50000  # 그 외 5억
CAPITAL_AREA = ("서울", "경기", "인천")
TREND_CAUTION = -3.0  # 매매가 하락률(%) 주의
TREND_DANGER = -10.0  # 위험

STATUS_ORDER = {"danger": 3, "caution": 2, "good": 1, "unknown": 0}


@dataclass
class Target:
    b_code: str
    main_no: str
    sub_no: str
    dong: str
    sido: str
    house_type: str
    deposit: float
    area: float | None = None
    senior_debt: float = 0
    official_price: float | None = None
    building_name: str = ""

    @property
    def jibun(self) -> str:
        return normalize_jibun(f"{self.main_no}-{self.sub_no or 0}")

    @property
    def umd_cd(self) -> str:
        return self.b_code[5:]


# ---------------------------------------------------------------- 유틸


def fmt_money(manwon: float | None) -> str:
    """만원 단위 숫자를 '3억 2,500만원' 형태로."""
    if manwon is None:
        return "-"
    v = int(round(manwon))
    eok, man = divmod(v, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def _same_dong(rec: dict, t: Target) -> bool:
    if rec.get("umd_cd"):
        return rec["umd_cd"] == t.umd_cd
    a, b = (rec.get("umd") or "").replace(" ", ""), (t.dong or "").replace(" ", "")
    if not a or not b:
        return False
    return a == b or a.endswith(b) or b.endswith(a)


def is_same_building(rec: dict, t: Target) -> bool:
    return rec.get("jibun") == t.jibun and _same_dong(rec, t)


def area_match(a: float | None, target: float | None, tol_ratio=0.05, tol_abs=2.0) -> bool:
    if a is None or target is None:
        return False
    return abs(a - target) <= max(tol_abs, target * tol_ratio)


def area_groups(records: list[dict]) -> list[dict]:
    """같은 건물 거래들의 전용면적을 비슷한 것끼리 묶는다."""
    areas = sorted(r["area"] for r in records if r.get("area"))
    groups: list[list[float]] = []
    for a in areas:
        if groups and a - groups[-1][0] <= 2.0:
            groups[-1].append(a)
        else:
            groups.append([a])
    out = [{"area": round(median(g), 2), "count": len(g)} for g in groups]
    return sorted(out, key=lambda g: g["area"])


def _within_days(rec: dict, days: int, today: date) -> bool:
    return date.fromisoformat(rec["date"]) >= today - timedelta(days=days)


def _recent_median(records: list[dict], field: str, n: int) -> float:
    recs = sorted(records, key=lambda r: r["date"], reverse=True)[:n]
    return median(r[field] for r in recs)


# ---------------------------------------------------------------- 시세 추정


def estimate(
    records: list[dict], field: str, t: Target, area: float | None, build_year: int | None, today: date
) -> dict | None:
    """같은 건물 → 주변 비슷한 주택 순으로 시세를 추정한다.

    records: 매매(field='price') 또는 전세(field='deposit') 거래 목록
    """
    same = [r for r in records if is_same_building(r, t) and (area is None or area_match(r["area"], area))]
    recent = [r for r in same if _within_days(r, 365, today)]
    if recent:
        return {
            "value": _recent_median(recent, field, 5),
            "count": min(len(recent), 5),
            "scope": "same",
            "confidence": "높음",
            "basis": f"같은 건물·비슷한 면적의 최근 1년 거래 {len(recent)}건 중 최근 {min(len(recent), 5)}건의 중앙값",
            "latest": max(r["date"] for r in recent),
        }
    if same:
        return {
            "value": _recent_median(same, field, 3),
            "count": min(len(same), 3),
            "scope": "same",
            "confidence": "보통",
            "basis": f"같은 건물·비슷한 면적 거래 (1년 이상 지난 거래 포함, {min(len(same), 3)}건 중앙값)",
            "latest": max(r["date"] for r in same),
        }
    if not area:
        return None
    near = [
        r
        for r in records
        if _same_dong(r, t)
        and r.get("area")
        and abs(r["area"] - area) <= area * 0.15
        and _within_days(r, 365, today)
        and (not build_year or not r.get("build_year") or abs(r["build_year"] - build_year) <= 7)
    ]
    if len(near) < 3:
        return None
    per_m2 = median(r[field] / r["area"] for r in near)
    return {
        "value": per_m2 * area,
        "count": len(near),
        "scope": "nearby",
        "confidence": "낮음",
        "basis": f"같은 동네 비슷한 면적·연식 주택 최근 1년 거래 {len(near)}건의 ㎡당 중앙값 × {area}㎡",
        "latest": max(r["date"] for r in near),
    }


def trend(trades: list[dict], t: Target, area: float | None, today: date) -> dict | None:
    """최근 6개월 vs 1~2년 전 매매가(㎡당) 변화율."""
    same = [r for r in trades if is_same_building(r, t) and r.get("area")]
    pool = same
    scope = "same"
    if len(same) < 4 and area:
        pool = [r for r in trades if _same_dong(r, t) and r.get("area") and abs(r["area"] - area) <= area * 0.15]
        scope = "nearby"
    recent = [r["price"] / r["area"] for r in pool if _within_days(r, 183, today)]
    old = [
        r["price"] / r["area"]
        for r in pool
        if not _within_days(r, 365, today) and _within_days(r, 730, today)
    ]
    if len(recent) < 2 or len(old) < 2:
        return None
    change = (median(recent) / median(old) - 1) * 100
    return {"change_pct": round(change, 1), "scope": scope, "recent_n": len(recent), "old_n": len(old)}


def series(trades: list[dict], rents: list[dict], t: Target, area: float | None) -> dict:
    """그래프용 데이터: 같은 건물(없으면 동네 ㎡당 환산) 매매·전세 거래 점과 월별 중앙값."""

    def pick(recs, field):
        same = [r for r in recs if is_same_building(r, t) and (area is None or area_match(r["area"], area))]
        if len(same) >= 3 or not area:
            return "same", [{"date": r["date"], "value": r[field]} for r in same]
        near = [r for r in recs if _same_dong(r, t) and r.get("area") and abs(r["area"] - area) <= area * 0.15]
        return "nearby", [{"date": r["date"], "value": round(r[field] / r["area"] * area)} for r in near]

    jeonse = [r for r in rents if not r.get("monthly")]
    s_scope, s_points = pick(trades, "price")
    j_scope, j_points = pick(jeonse, "deposit")

    def monthly(points):
        by: dict[str, list[float]] = {}
        for p in points:
            by.setdefault(p["date"][:7], []).append(p["value"])
        return [{"month": m, "value": round(median(v))} for m, v in sorted(by.items())]

    return {
        "trade": {"scope": s_scope, "points": sorted(s_points, key=lambda p: p["date"]), "monthly": monthly(s_points)},
        "jeonse": {"scope": j_scope, "points": sorted(j_points, key=lambda p: p["date"]), "monthly": monthly(j_points)},
    }


# ---------------------------------------------------------------- 건축물대장


RESIDENTIAL = ("공동주택", "단독주택", "아파트", "다세대", "연립", "다가구", "다중주택")


def summarize_building(titles: list[dict], recaps: list[dict]) -> dict | None:
    if not titles and not recaps:
        return None
    # 주건축물 중 주택 용도를 대표로 (아파트는 지하주차장 등 부속 건물이 먼저 올 수 있음)
    def rank(x):
        return (x.get("mainAtchGbCdNm", "주건축물") == "주건축물", any(k in x.get("mainPurpsCdNm", "") for k in RESIDENTIAL))

    main = max(titles, key=rank) if titles else recaps[0]
    recap = recaps[0] if recaps else {}
    purposes = sorted({x.get("mainPurpsCdNm", "") for x in titles + recaps if x.get("mainPurpsCdNm")})
    etc = sorted({x.get("etcPurps", "") for x in titles if x.get("etcPurps")})
    approval = main.get("useAprDay", "")
    approval_year = int(approval[:4]) if approval[:4].isdigit() else None
    # 위반건축물 표시 필드가 있으면 사용 (필드명이 확인되지 않아 'viol' 이 들어간 키를 검사)
    violation = any(
        ("viol" in k.lower() or "위반" in k) and str(v).strip().upper() in ("Y", "1", "위반")
        for x in titles + recaps
        for k, v in x.items()
    )
    def count(x):
        for k in ("hhldCnt", "hoCnt", "fmlyCnt"):
            v = str(x.get(k, "")).strip()
            if v and v != "0":
                return v
        return ""

    households = count(recap) or count(main)
    if not households and len(titles) > 1:
        total = sum(int(t.get("hhldCnt") or 0) for t in titles if str(t.get("hhldCnt", "")).isdigit())
        households = str(total) if total else ""
    main_titles = [t for t in titles if t.get("mainAtchGbCdNm", "주건축물") == "주건축물"]
    return {
        "name": recap.get("bldNm") or main.get("bldNm", ""),
        "purposes": purposes,
        "etc_purposes": etc if len(etc) <= 3 else etc[:3] + [f"외 {len(etc) - 3}건"],
        "approval_date": approval,
        "approval_year": approval_year,
        "structure": main.get("strctCdNm", ""),
        "floors": main.get("grndFlrCnt", ""),
        "households": households,
        "dong_count": len(main_titles) or len(titles),
        "violation": violation,
    }


def latest_house_price(prices: list[dict]) -> float | None:
    """건축물대장 주택가격(원 단위로 오는 것으로 추정) → 만원."""
    best = None
    for p in prices:
        raw = p.get("hsprc") or p.get("housePrc") or ""
        try:
            won = float(str(raw).replace(",", ""))
        except ValueError:
            continue
        day = p.get("crtnDay") or p.get("stdDay") or ""
        if best is None or day > best[0]:
            best = (day, won)
    if not best or best[1] <= 0:
        return None
    return best[1] / 10000


# ---------------------------------------------------------------- 항목별 판단


def check(id_, title, status, value, summary, detail, basis="") -> dict:
    return {"id": id_, "title": title, "status": status, "value": value, "summary": summary, "detail": detail, "basis": basis}


def check_ratio(t: Target, sale: dict | None) -> dict:
    title = "전세가율"
    if not sale:
        return check(
            "ratio", title, "unknown", "판단 불가", "비교할 매매 거래가 없어요",
            "최근 2년간 같은 건물이나 주변 비슷한 주택의 매매 거래를 찾지 못했어요. 공인중개사·감정평가 등으로 매매 시세를 꼭 확인하세요.",
        )
    total = t.deposit + (t.senior_debt or 0)
    ratio = total / sale["value"] * 100
    debt_note = f" (보증금 + 선순위 채권 {fmt_money(t.senior_debt)})" if t.senior_debt else ""
    if ratio <= JEONSE_RATIO_GOOD:
        status, summary = "good", "매매가 대비 보증금 비율이 안정적이에요"
    elif ratio <= JEONSE_RATIO_CAUTION:
        status, summary = "caution", "보증금이 매매가에 가까운 편이에요"
    elif ratio < 100:
        status, summary = "danger", "집값이 조금만 내려도 보증금을 돌려받기 어려울 수 있어요"
    else:
        status, summary = "danger", "보증금이 매매가보다 많아요 (깡통전세 위험)"
    detail = (
        f"추정 매매가 {fmt_money(sale['value'])} 대비 {fmt_money(total)}{debt_note} = {ratio:.0f}%. "
        f"{JEONSE_RATIO_GOOD}% 이하면 양호, {JEONSE_RATIO_CAUTION}% 초과면 위험으로 봅니다."
    )
    if sale["scope"] == "nearby":
        detail += " 같은 건물 거래가 없어 주변 시세로 추정했으니 오차가 클 수 있어요."
    if not t.senior_debt:
        detail += " 등기부의 근저당(채권최고액)을 입력하면 더 정확해져요."
    return check("ratio", title, status, f"{ratio:.0f}%", summary, detail, f"{sale['basis']} · 신뢰도 {sale['confidence']}")


def check_market(t: Target, jeonse: dict | None) -> dict:
    title = "주변 전세 시세 비교"
    if not jeonse:
        return check(
            "market", title, "unknown", "판단 불가", "비교할 전세 거래가 없어요",
            "최근 같은 건물이나 주변 비슷한 주택의 전세 거래를 찾지 못했어요.",
        )
    r = t.deposit / jeonse["value"]
    pct = (r - 1) * 100
    value = f"{'+' if pct >= 0 else ''}{pct:.0f}%"
    if r < MARKET_LOW:
        status, summary = "caution", "시세보다 많이 싸요 — 싼 이유를 꼭 확인하세요"
        detail = "주변보다 보증금이 크게 낮은 매물은 선순위 채권(근저당)이나 집주인 세금 체납 등 숨은 위험이 있을 수 있어요."
    elif r > MARKET_HIGH:
        status, summary = "caution", "주변 전세 시세보다 비싸요"
        detail = "시세보다 높은 보증금은 나중에 집주인이 다음 세입자를 구하지 못해 보증금 반환이 늦어질 수 있어요."
    else:
        status, summary = "good", "주변 전세 시세와 비슷해요"
        detail = "보증금이 주변 전세 거래 수준이에요."
    detail = f"주변 전세 시세 {fmt_money(jeonse['value'])}, 입력한 보증금 {fmt_money(t.deposit)}. " + detail
    return check("market", title, status, value, summary, detail, f"{jeonse['basis']} · 신뢰도 {jeonse['confidence']}")


def check_guarantee(t: Target, official: float | None, official_source: str) -> dict:
    title = "보증보험 가입 가능성 (추정)"
    limit = HUG_LIMIT_CAPITAL if t.sido.startswith(CAPITAL_AREA) else HUG_LIMIT_OTHER
    region = "수도권" if limit == HUG_LIMIT_CAPITAL else "비수도권"
    if t.deposit > limit:
        return check(
            "guarantee", title, "danger", "한도 초과", f"보증금이 {region} 보증 한도({fmt_money(limit)})를 넘어요",
            "HUG 전세보증금반환보증은 보증금 한도가 있어 가입이 어려워요. 다른 보증기관(HF·SGI) 조건을 확인하세요.",
        )
    if not official:
        return check(
            "guarantee", title, "unknown", "공시가격 필요", "공시가격을 입력하면 계산해 드려요",
            "부동산공시가격알리미(realtyprice.kr)에서 해당 호의 공동주택 공시가격을 확인해 입력하세요.",
        )
    cap = official * HUG_OFFICIAL_RATE
    total = t.deposit + (t.senior_debt or 0)
    note = " 아파트는 KB시세 등 다른 기준이 먼저 적용될 수 있어요." if t.house_type == "apt" else ""
    if t.house_type == "offi":
        note = " 오피스텔은 공시가격 대신 기준시가 등 다른 기준이 적용될 수 있어요."
    if total <= cap:
        status, summary = "good", "공시가격 기준 한도 안에 있어요"
    else:
        status, summary = "danger", "공시가격 기준 한도를 넘어 가입이 어려울 수 있어요"
    detail = (
        f"공시가격 {fmt_money(official)} × {HUG_OFFICIAL_RATE * 100:.0f}% = {fmt_money(cap)}, "
        f"보증금{' + 선순위 채권' if t.senior_debt else ''} {fmt_money(total)}.{note} "
        "실제 가입 가능 여부는 HUG·HF·SGI에 꼭 확인하세요."
    )
    return check("guarantee", title, status, f"한도 {fmt_money(cap)}", summary, detail, f"공시가격 출처: {official_source}")


def check_building(t: Target, b: dict | None) -> dict:
    title = "건축물대장 (용도)"
    if not b:
        return check(
            "building", title, "unknown", "정보 없음", "건축물대장을 찾지 못했어요",
            "정부24에서 건축물대장을 직접 발급해 용도와 위반건축물 여부를 확인하세요.",
        )
    purposes = ", ".join(b["purposes"]) or "확인 불가"
    joined = " ".join(b["purposes"] + b["etc_purposes"])
    age = f", 사용승인 {b['approval_year']}년" if b.get("approval_year") else ""
    if b.get("violation"):
        return check(
            "building", title, "danger", "위반건축물", "위반건축물로 표시돼 있어요",
            "위반건축물은 전세대출·보증보험이 거절될 수 있어요. 건축물대장을 발급해 위반 내용을 꼭 확인하세요.",
            f"주용도: {purposes}{age}",
        )
    if any(k in joined for k in RESIDENTIAL):
        return check("building", title, "good", "주택", "주택 용도의 건물이에요", f"주용도: {purposes}{age}.", "건축물대장 표제부")
    if "업무시설" in joined or "오피스텔" in joined:
        status = "good" if t.house_type == "offi" else "caution"
        return check(
            "building", title, status, "오피스텔", "업무시설(오피스텔) 건물이에요",
            f"주용도: {purposes}{age}. 오피스텔은 전입신고가 가능한지(주거용 사용) 계약 전에 확인하세요.",
            "건축물대장 표제부",
        )
    if "근린생활" in joined:
        return check(
            "building", title, "danger", "근린생활시설", "주택이 아닌 근린생활시설이에요",
            f"주용도: {purposes}{age}. 근린생활시설을 주택으로 쓰는 '근생빌라'는 전세대출·보증보험이 거절될 수 있어요.",
            "건축물대장 표제부",
        )
    return check("building", title, "caution", purposes, "주택 용도인지 확인이 필요해요", f"주용도: {purposes}{age}.", "건축물대장 표제부")


def check_trend(tr: dict | None) -> dict:
    title = "매매가 추이"
    if not tr:
        return check("trend", title, "unknown", "판단 불가", "추이를 볼 거래가 부족해요", "최근 2년간 비교할 매매 거래가 충분하지 않아요.")
    c = tr["change_pct"]
    value = f"{'+' if c >= 0 else ''}{c}%"
    if c <= TREND_DANGER:
        status, summary = "danger", "매매가가 크게 떨어지고 있어요"
    elif c <= TREND_CAUTION:
        status, summary = "caution", "매매가가 조금씩 떨어지고 있어요"
    else:
        status, summary = "good", "매매가가 안정적이에요"
    scope = "같은 건물" if tr["scope"] == "same" else "같은 동네 비슷한 면적"
    detail = (
        f"{scope} 최근 6개월 거래({tr['recent_n']}건)의 ㎡당 가격이 1~2년 전({tr['old_n']}건)보다 {value} 변했어요. "
        "집값이 떨어지면 계약 만기 때 보증금을 돌려받기 어려워질 수 있어요."
    )
    return check("trend", title, status, value, summary, detail, f"{scope} 매매 실거래가")


# ---------------------------------------------------------------- 종합


def overall(checks: list[dict]) -> dict:
    known = [c for c in checks if c["status"] != "unknown"]
    dangers = [c for c in checks if c["status"] == "danger"]
    cautions = [c for c in checks if c["status"] == "caution"]
    if not known:
        return {"status": "unknown", "score": None, "headline": "판단할 데이터가 부족해요", "message": "직접 확인이 필요한 항목을 아래에서 확인하세요."}
    # 게이지 점수: 양호 70~100 / 주의 40~69 / 위험 0~39 구간에 들어가도록
    if dangers:
        score = max(5, 35 - 10 * (len(dangers) - 1) - 3 * len(cautions))
    elif cautions:
        score = max(42, 65 - 8 * (len(cautions) - 1))
    else:
        score = 90 if len(known) >= 3 else 78
    if dangers:
        worst = dangers[0]
        return {"status": "danger", "score": score, "headline": f"위험 신호가 {len(dangers)}개 있어요", "message": worst["summary"]}
    if cautions:
        return {"status": "caution", "score": score, "headline": "꼼꼼한 확인이 필요해요", "message": cautions[0]["summary"]}
    return {"status": "good", "score": score, "headline": "큰 위험 신호는 없어요", "message": "그래도 등기부등본 확인은 꼭 하세요."}


def diagnose(
    t: Target,
    trades: list[dict],
    rents: list[dict],
    titles: list[dict],
    recaps: list[dict],
    prices: list[dict],
    today: date | None = None,
) -> dict:
    today = today or date.today()
    jeonse_recs = [r for r in rents if not r.get("monthly")]

    same_recs = [r for r in trades + jeonse_recs if is_same_building(r, t)]
    groups = area_groups(same_recs)
    area = t.area
    area_source = "input"
    if not area and groups:
        area = max(groups, key=lambda g: g["count"])["area"]
        area_source = "auto"

    building = summarize_building(titles, recaps)
    build_year = building.get("approval_year") if building else None
    if not build_year:
        years = [r["build_year"] for r in same_recs if r.get("build_year")]
        build_year = years[0] if years else None

    sale = estimate(trades, "price", t, area, build_year, today)
    jeonse = estimate(jeonse_recs, "deposit", t, area, build_year, today)
    tr = trend(trades, t, area, today)

    official, official_source = t.official_price, "직접 입력"
    if not official:
        official = latest_house_price(prices)
        official_source = "건축물대장 주택가격"

    checks = [
        check_ratio(t, sale),
        check_market(t, jeonse),
        check_guarantee(t, official, official_source),
        check_building(t, building),
        check_trend(tr),
    ]
    names = [r["name"] for r in same_recs if r.get("name")]
    return {
        "overall": overall(checks),
        "checks": checks,
        "estimates": {"sale": sale, "jeonse": jeonse, "official_price": official, "trend": tr},
        "area": {"selected": area, "source": area_source if area else None, "groups": groups},
        "building": building,
        "complex_name": names[0] if names else (building or {}).get("name") or t.building_name,
        "series": series(trades, rents, t, area),
        "counts": {
            "same_trades": sum(1 for r in trades if is_same_building(r, t)),
            "same_jeonse": sum(1 for r in jeonse_recs if is_same_building(r, t)),
            "district_trades": len(trades),
            "district_rents": len(rents),
        },
    }
