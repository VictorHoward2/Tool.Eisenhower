# src/db/db.py
import os
import sqlite3
import json
from pathlib import Path
from typing import List
from models.task import Task

APP_DIR = Path(os.getenv("APPDATA") or Path.home()) / "Eisenhower3x3"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "tasks.sqlite3"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    importance TEXT NOT NULL,
    urgency TEXT NOT NULL,
    due_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    status TEXT DEFAULT 'todo',
    tags TEXT,
    order_in_cell INTEGER DEFAULT 0
);
"""

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db_if_needed():
    created = False
    if not DB_PATH.exists():
        # create empty db file by connecting
        conn = get_conn()
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()
        created = True
    else:
        # ensure table exists
        conn = get_conn()
        conn.executescript(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()
    return str(DB_PATH)

def task_row_to_task(row) -> Task:
    d = dict(row)
    # tags stored as JSON text
    tags = []
    if d.get("tags"):
        try:
            tags = json.loads(d["tags"])
        except Exception:
            tags = []
    d["tags"] = tags
    return Task.from_dict(d)

def load_all_tasks() -> List[Task]:
    init_db_if_needed()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks")
    rows = cur.fetchall()
    conn.close()
    return [task_row_to_task(r) for r in rows]

def save_task(task: Task):
    init_db_if_needed()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tasks (id, title, description, importance, urgency, due_date,
                           created_at, updated_at, status, tags, order_in_cell)
        VALUES (:id, :title, :description, :importance, :urgency, :due_date,
                :created_at, :updated_at, :status, :tags, :order_in_cell)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            importance=excluded.importance,
            urgency=excluded.urgency,
            due_date=excluded.due_date,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            status=excluded.status,
            tags=excluded.tags,
            order_in_cell=excluded.order_in_cell
        """,
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "importance": task.importance,
            "urgency": task.urgency,
            "due_date": task.due_date,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "status": task.status,
            "tags": json.dumps(task.tags),
            "order_in_cell": 0,
        },
    )
    conn.commit()
    conn.close()

def delete_task(task_id: str):
    init_db_if_needed()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
