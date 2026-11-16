# 전세체크 (jeonse-check)

주소와 보증금을 입력하면 공공데이터로 **전세 위험 신호**를 진단하는 웹 서비스입니다.

- 운영 주소: http://52.63.57.83 (AWS 시드니, 서버를 다시 만들면 IP 가 바뀝니다)
- 대상 주택: 아파트 · 연립다세대(빌라) · 오피스텔

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
  tests/          pytest
frontend/   React 19 + Vite — 주소 검색, 리포트(게이지·항목 카드·그래프·지도·체크리스트)
  nginx.conf      운영: 정적 파일 + /api 프록시
deploy/     AWS 생성·삭제, 서버 최초 설정, 배포 스크립트
.github/workflows/deploy.yml   push 시 테스트·빌드 검사 → EC2 자동 배포
docker-compose.yml
```

## 처음 설정

1. API 키 준비
   - 공공데이터포털: 국토교통부 아파트·연립다세대·오피스텔 매매/전월세 실거래가, 건축HUB 건축물대장정보 서비스 활용신청
     (계정당 인증키 1개를 모든 API 에 공통으로 사용)
   - 카카오디벨로퍼스: 앱 생성 → 카카오맵 사용 설정 ON → 플랫폼 키에서 REST API 키·JavaScript 키 확인,
     JavaScript SDK 도메인에 `http://localhost:5173` 과 운영 주소(`http://서버IP`) 등록
2. 키 입력 (git 에 올라가지 않음)
   - `backend/.env` ← `DATA_GO_KR_API_KEY`(Decoding 키), `KAKAO_REST_API_KEY`
   - `frontend/.env` ← `VITE_KAKAO_JS_KEY`
3. 설치: `npm run setup`

## 로컬 실행

```bash
npm run dev     # 백엔드(8000) + 프론트(5173) 동시 실행 → http://localhost:5173
npm test        # 백엔드 테스트
npm run build   # 프론트 빌드
```

## Docker

```bash
# backend/.env (필수), frontend/.env (지도용, 선택) 를 준비한 뒤
export VITE_KAKAO_JS_KEY=$(grep ^VITE_KAKAO_JS_KEY= frontend/.env | cut -d= -f2-)
docker compose up -d --build     # http://localhost  (nginx → /api 는 backend 로 프록시)
```

- 키는 이미지에 들어가지 않습니다 (`.dockerignore` 에서 `.env` 제외, 실행 시 `env_file` 로 주입).
- 실거래가 캐시는 `cache-data` 볼륨에 저장되어 재배포해도 유지됩니다.

## AWS 배포 (Git Bash 에서 실행)

사전 준비: AWS CLI v2, `aws login`, `backend/.env`, `frontend/.env`

```bash
bash deploy/aws-create.sh --dry-run   # 권한만 확인 (아무것도 만들지 않음, 비용 없음)
bash deploy/aws-create.sh             # 생성 → 서버 설정 → 배포 (10~15분, 과금 시작)
```

만드는 것 (모두 `Project=jeonse-check` 태그, 리전 `ap-southeast-2` 시드니):

| 리소스 | 내용 |
| --- | --- |
| EC2 | Ubuntu 24.04, t3.micro, 디스크 20GB (스왑 2GB 설정) |
| 고정 IP | 서버를 껐다 켜도 주소 유지 |
| 보안그룹 `jeonse-check-sg` | 80(웹) 전체 허용, 22(SSH) 키 인증만 |
| 키페어 `jeonse-check-key` | `~/.ssh/jeonse-check-key.pem` 에 저장 — 분실하면 서버 접속 불가 |

생성 후 할 일:
1. 카카오 JavaScript SDK 도메인에 `http://서버IP` 추가 (안 하면 지도만 안 나옴)
2. GitHub 저장소 **Settings → Secrets and variables → Actions** 에 입력

   | 탭 | 이름 | 값 |
   | --- | --- | --- |
   | Secrets | `EC2_HOST` | 서버 IP |
   | Secrets | `EC2_USER` | `ubuntu` |
   | Secrets | `EC2_SSH_KEY` | `~/.ssh/jeonse-check-key.pem` 파일 내용 전체 (BEGIN~END 줄 포함) |
   | Variables | `DEPLOY_ENABLED` | `true` |

### 자동 배포

`main` 브랜치에 push 하면 GitHub Actions 가
1. 백엔드 테스트 · docker-compose 검사 · 이미지 빌드 · 컨테이너 기동 검사 (`.env` 가 이미지에 없는지 포함)
2. `DEPLOY_ENABLED=true` 이면 EC2 에 SSH 접속 → `deploy/deploy.sh` (git pull → 재빌드 → 헬스 체크)

서버에서 직접 배포: `ssh -i ~/.ssh/jeonse-check-key.pem ubuntu@서버IP 'bash ~/jeonse-check/deploy/deploy.sh'`

### 비용과 삭제

| 상태 | 월 비용(대략) |
| --- | --- |
| 실행 중 | 약 $15 |
| 정지 (AWS 콘솔에서 인스턴스 중지) | 약 $5.5 (디스크 + 고정 IP) |
| 삭제 | $0 |

```bash
bash deploy/aws-destroy.sh --dry-run   # 삭제 대상만 확인
bash deploy/aws-destroy.sh             # 프로젝트 이름(jeonse-check) 입력 후 영구 삭제
```

삭제 후에는 GitHub 저장소 Variables 의 `DEPLOY_ENABLED` 를 `false` 로 바꾸세요 (아니면 push 할 때마다 배포 단계가 실패).
로컬 `.pem`·`.env` 와 GitHub 저장소는 삭제되지 않습니다.

## 알려진 제한

- 연립다세대 **매매** 실거래가 API 가 응답하지 않으면 빌라의 전세가율·매매가 추이는 "실거래 데이터를 받지 못했어요"로 표시됩니다.
- 공시가격은 자동 조회하지 않습니다 (건축물대장 주택가격은 공동주택의 동·호를 특정할 수 없음). 사용자가 입력합니다.
- 단독·다가구는 실거래 지번이 비공개라 같은 건물 비교가 불가능해 대상에서 제외했습니다.
