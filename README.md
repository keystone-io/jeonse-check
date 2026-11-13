# 전세체크 (jeonse-check)

주소와 보증금을 입력하면 공공데이터로 **전세 위험 신호**를 진단하는 웹 서비스입니다.

| 진단 항목 | 방법 | 데이터 |
| --- | --- | --- |
| 전세가율 | (보증금 + 선순위 채권) ÷ 추정 매매가 | 국토교통부 매매 실거래가 |
| 주변 전세 시세 | 보증금 ÷ 같은 건물·주변 전세 거래 중앙값 | 국토교통부 전월세 실거래가 |
| 보증보험 가능성(추정) | 공시가격 × 126% 이내인지, 보증금 한도(수도권 7억 / 그 외 5억) | 사용자 입력 공시가격 |
| 건축물 용도 | 주택 / 오피스텔 / 근린생활시설 (위반건축물 여부는 API 에 없어 체크리스트로 안내) | 건축HUB 건축물대장 |
| 매매가 추이 | 최근 6개월 vs 1~2년 전 ㎡당 가격 | 매매 실거래가 |

> 진단 결과는 참고용입니다. 등기부등본(근저당·압류), 집주인 세금 체납은 공공데이터로 확인할 수 없습니다.
> 판단 기준(70%/80% 등)은 [backend/diagnosis.py](backend/diagnosis.py) 상단에서 바꿀 수 있습니다.

## 구조

```
backend/    FastAPI — 외부 API 프록시 + 진단 계산 (키는 서버에만 보관)
  main.py         /api/health, /api/address, /api/diagnose
  clients.py      카카오 로컬, 공공데이터포털(실거래가·건축물대장) 호출·정규화
  diagnosis.py    진단 로직 (외부 호출 없음)
  cache.py        SQLite 캐시 (backend/data/, git 제외)
frontend/   React 19 + Vite — 주소 검색, 리포트(게이지·항목 카드·그래프·지도·체크리스트)
```

## 처음 설정

1. API 키 준비
   - 공공데이터포털: 국토교통부 아파트·연립다세대·오피스텔 매매/전월세 실거래가, 건축HUB 건축물대장정보 서비스 활용신청
   - 카카오디벨로퍼스: 앱 생성 → 카카오맵 사용 설정 ON → 플랫폼 키에서 REST API 키·JavaScript 키 확인, JavaScript SDK 도메인에 `http://localhost:5173` 등록
2. 키 입력 (git 에 올라가지 않음)
   - `backend/.env` ← `DATA_GO_KR_API_KEY`(Decoding 키), `KAKAO_REST_API_KEY`
   - `frontend/.env` ← `VITE_KAKAO_JS_KEY`
3. 설치: `npm run setup`

## 실행

```bash
npm run dev     # 백엔드(8000) + 프론트(5173) 동시 실행 → http://localhost:5173
npm test        # 백엔드 테스트
npm run build   # 프론트 빌드
```
