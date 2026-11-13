FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CACHE_PATH=/app/data/cache.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py clients.py diagnosis.py cache.py ./

# root 가 아닌 사용자로 실행. 캐시 폴더(/app/data)는 docker-compose 볼륨으로 유지된다.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data \
    && chown app:app /app/data
USER app

EXPOSE 8000

# API 키는 이미지에 넣지 않고 docker-compose 의 env_file(backend/.env)로 주입한다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
