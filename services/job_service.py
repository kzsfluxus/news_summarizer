from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from uuid import uuid4

from config import JOBS_DIR


@dataclass
class JobState:
    job_id: str
    stage: str = "idle"
    progress: int = 0
    message: str = "Készen áll"
    html: str = ""
    error: str = ""
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "html": self.html,
            "error": self.error,
            "stats": self.stats,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create(self) -> JobState:
        job = JobState(job_id=uuid4().hex)
        with self._lock:
            self._jobs[job.job_id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
        self._persist(job)

    def _persist(self, job: JobState) -> None:
        path = Path(JOBS_DIR) / f"{job.job_id}.json"
        path.write_text(json.dumps(job.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
