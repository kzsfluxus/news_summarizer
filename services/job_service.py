from __future__ import annotations

import json
from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from services.db_service import get_active_job, get_job, upsert_job

RUNNING_STAGES = {"rss", "scrape", "markdown", "ollama", "html"}


@dataclass
class JobState:
    job_id: str
    stage: str = "idle"
    progress: int = 0
    message: str = "Készen áll"
    html: str = ""
    error: str = ""
    stats: dict = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        return self.stage in RUNNING_STAGES

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

    def _save(self) -> None:
        upsert_job(
            job_id=self.job_id,
            stage=self.stage,
            progress=self.progress,
            message=self.message,
            html=self.html,
            error=self.error,
            stats=json.dumps(self.stats, ensure_ascii=False),
        )

    @classmethod
    def _from_row(cls, row: dict) -> "JobState":
        stats = row.get("stats", "{}")
        if isinstance(stats, str):
            try:
                stats = json.loads(stats)
            except Exception:
                stats = {}
        return cls(
            job_id=row["job_id"],
            stage=row["stage"],
            progress=row["progress"],
            message=row["message"],
            html=row.get("html", ""),
            error=row.get("error", ""),
            stats=stats,
        )


class JobRegistry:
    """
    Szálbiztos job-nyilvántartó SQLite háttérrel.
    Az in-memory cache csak a futó sessionre vonatkozik;
    a DB az egyetlen megbízható forrás.
    """

    def __init__(self) -> None:
        self._cache: dict[str, JobState] = {}
        self._lock = Lock()

    def active_job(self) -> JobState | None:
        """Visszaadja az éppen futó jobot (DB-ből), ha van."""
        row = get_active_job()
        if row:
            return JobState._from_row(row)
        return None

    def create(self) -> JobState:
        job = JobState(job_id=uuid4().hex)
        job._save()
        with self._lock:
            self._cache[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            if job_id in self._cache:
                return self._cache[job_id]
        # Ha nincs cache-ben (pl. szerver újraindítás után), DB-ből töltjük
        row = get_job(job_id)
        if row:
            job = JobState._from_row(row)
            with self._lock:
                self._cache[job_id] = job
            return job
        return None

    def update(self, job_id: str, **changes) -> None:
        with self._lock:
            job = self._cache.get(job_id)
            if job is None:
                row = get_job(job_id)
                if row is None:
                    raise KeyError(f"Ismeretlen job_id: {job_id}")
                job = JobState._from_row(row)
                self._cache[job_id] = job
            for key, value in changes.items():
                setattr(job, key, value)
        job._save()
