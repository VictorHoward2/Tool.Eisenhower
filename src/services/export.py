# src/services/export.py
import csv
import json
from typing import List
from pathlib import Path
import pandas as pd
from models.task import Task
from db import db

def export_tasks_to_csv(tasks: List[Task], filepath: str):
    path = Path(filepath)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["id","title","description","importance","urgency","due_date","created_at","updated_at","status","tags"]
        writer.writerow(header)
        for t in tasks:
            writer.writerow([
                t.id,
                t.title,
                t.description or "",
                t.importance,
                t.urgency,
                t.due_date or "",
                t.created_at,
                t.updated_at or "",
                t.status,
                json.dumps(t.tags or []),
            ])

def export_tasks_to_excel(tasks: List[Task], filepath: str):
    # use pandas for ease
    rows = []
    for t in tasks:
        rows.append({
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "importance": t.importance,
            "urgency": t.urgency,
            "due_date": t.due_date or "",
            "created_at": t.created_at,
            "updated_at": t.updated_at or "",
            "status": t.status,
            "tags": json.dumps(t.tags or []),
        })
    df = pd.DataFrame(rows)
    df.to_excel(filepath, index=False)

def import_tasks_from_csv(filepath: str, overwrite_duplicates: bool = False) -> List[Task]:
    path = Path(filepath)
    tasks = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tags = []
            try:
                tags = json.loads(row.get("tags") or "[]")
            except Exception:
                tags = []
            t = Task(
                id=row.get("id") or None,
                title=row.get("title","").strip(),
                description=row.get("description",""),
                importance=row.get("importance") or "medium",
                urgency=row.get("urgency") or "medium",
                due_date=row.get("due_date") or None,
            )
            # ensure id exists
            if not t.id:
                import uuid
                t.id = str(uuid.uuid4())
            t.tags = tags
            # created_at/updated_at from CSV if present
            if row.get("created_at"):
                t.created_at = row.get("created_at")
            if row.get("updated_at"):
                t.updated_at = row.get("updated_at")
            # check existing
            if not overwrite_duplicates:
                existing = [x for x in db.load_all_tasks() if x.id == t.id]
                if existing:
                    continue
            db.save_task(t)
            tasks.append(t)
    return tasks
