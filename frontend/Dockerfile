# 1) React(Vite) 빌드
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# 카카오 JavaScript 키는 빌드 시 JS 파일에 들어간다 (브라우저에서 쓰는 공개 키, 등록 도메인에서만 동작).
# docker-compose 가 frontend/.env 값을 build arg 로 넘겨준다. 비어 있으면 지도만 숨겨진다.
ARG VITE_KAKAO_JS_KEY=""
RUN VITE_KAKAO_JS_KEY="$VITE_KAKAO_JS_KEY" npm run build

# 2) Nginx 로 정적 파일 서비스 + /api 를 backend 컨테이너로 프록시
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
