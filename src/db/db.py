# src/db/db.py
# Stub/placeholder for DB functions (sẽ mở rộng ở bước persistence)
import os
from pathlib import Path

APP_DIR = Path(os.getenv("APPDATA") or Path.home()) / "Eisenhower3x3"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "tasks.sqlite3"

def init_db_if_needed():
    # placeholder: we'll implement sqlite creation later (step 7)
    if not DB_PATH.exists():
        # TODO: create sqlite file / tables
        DB_PATH.write_text("")  # temporary
    return str(DB_PATH)
