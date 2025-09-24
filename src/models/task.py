from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
import uuid
import json

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    importance: str = "medium"   # low|medium|high
    urgency: str = "medium"      # low|medium|high
    due_date: Optional[str] = None  # "YYYY-MM-DD" or None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    status: str = "todo"
    tags: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        # ensure fields exist and types compatible
        if "tags" in d and isinstance(d["tags"], str):
            try:
                d["tags"] = json.loads(d["tags"])
            except Exception:
                d["tags"] = []
        return Task(**d)
