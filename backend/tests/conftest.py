import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["CACHE_PATH"] = str(Path(__file__).resolve().parent / ".test-cache.sqlite3")
