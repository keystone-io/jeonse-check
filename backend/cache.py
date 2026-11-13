"""SQLite 기반 간단 캐시.

실거래가 API 는 "시군구 + 계약월" 단위로 데이터를 주기 때문에, 한 번 받은 달의 데이터는
같은 구의 다른 주소를 진단할 때도 재사용한다. 서버를 재시작해도 남도록 파일에 저장한다.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_PATH = Path(os.getenv("CACHE_PATH", Path(__file__).parent / "data" / "cache.sqlite3"))


class Cache:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)"
        )
        self._conn.commit()

    def get(self, key: str):
        with self._lock:
            row = self._conn.execute("SELECT value, expires FROM cache WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        value, expires = row
        if expires < time.time():
            return None
        return json.loads(value)

    def set(self, key: str, value, ttl_seconds: float) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
                (key, payload, time.time() + ttl_seconds),
            )
            self._conn.commit()

    def purge_expired(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE expires < ?", (time.time(),))
            self._conn.commit()
