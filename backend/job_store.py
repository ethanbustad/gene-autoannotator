import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso():
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS annotation_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    output_path TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )

    def create_job(self, request: dict[str, Any]):
        job_id = str(uuid.uuid4())
        created_at = _now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO annotation_jobs (
                    id, status, request_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (job_id, "queued", json.dumps(request), created_at),
            )
        return self.get_job(job_id)

    def get_job(self, job_id):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM annotation_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def mark_running(self, job_id):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE annotation_jobs
                SET status = ?, started_at = ?
                WHERE id = ?
                """,
                ("running", _now_iso(), job_id),
            )

    def mark_completed(self, job_id, result: dict[str, Any], output_path=None):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE annotation_jobs
                SET status = ?, result_json = ?, output_path = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    json.dumps(result),
                    output_path,
                    _now_iso(),
                    job_id,
                ),
            )

    def mark_failed(self, job_id, error):
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE annotation_jobs
                SET status = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                ("failed", str(error), _now_iso(), job_id),
            )

    def _row_to_job(self, row):
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return {
            "id": row["id"],
            "status": row["status"],
            "request": json.loads(row["request_json"]),
            "result": result,
            "error": row["error"],
            "output_path": row["output_path"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "result_available": result is not None,
        }
