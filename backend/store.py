"""Small, durable SQLite store. Media stays on disk; the database stores metadata."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "studio.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    record TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS asset_hash ON assets(sha256);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, record TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS job_queue ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS presets (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=15)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=15000")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def get(self, table: str, ident: str) -> dict | None:
        if table not in {"jobs", "assets", "presets"}:
            raise ValueError("Unknown table")
        with self.connection() as db:
            row = db.execute(f"SELECT record FROM {table} WHERE id=?", (ident,)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, table: str, limit: int = 100, offset: int = 0) -> list[dict]:
        if table not in {"jobs", "assets", "presets"}:
            raise ValueError("Unknown table")
        with self.connection() as db:
            rows = db.execute(
                f"SELECT record FROM {table} ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            return [json.loads(row[0]) for row in rows]

    def count(self, table: str) -> int:
        if table not in {"jobs", "assets", "presets"}:
            raise ValueError("Unknown table")
        with self.connection() as db:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def insert(self, table: str, record: dict):
        payload = json.dumps(record)
        with self.connection() as db:
            if table == "jobs":
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", (
                    record["id"], record["status"], record["created_at"], record["updated_at"], payload
                ))
            elif table == "assets":
                db.execute("INSERT INTO assets VALUES (?,?,?,?)", (
                    record["id"], record["sha256"], record["created_at"], payload
                ))
            elif table == "presets":
                db.execute("INSERT INTO presets VALUES (?,?,?)", (
                    record["id"], record["created_at"], payload
                ))
            else:
                raise ValueError("Unknown table")

    def update_job(self, ident: str, changes: dict) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT record FROM jobs WHERE id=?", (ident,)).fetchone()
            if not row:
                return None
            record = json.loads(row[0])
            record.update(changes)
            record["updated_at"] = now()
            db.execute("UPDATE jobs SET status=?, updated_at=?, record=? WHERE id=?", (
                record["status"], record["updated_at"], json.dumps(record), ident
            ))
            return record

    def delete(self, table: str, ident: str):
        if table not in {"jobs", "assets", "presets"}:
            raise ValueError("Unknown table")
        with self.connection() as db:
            db.execute(f"DELETE FROM {table} WHERE id=?", (ident,))

    def by_hash(self, digest: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT record FROM assets WHERE sha256=? LIMIT 1", (digest,)).fetchone()
            return json.loads(row[0]) if row else None

    def asset_references(self, ident: str) -> list[str]:
        with self.connection() as db:
            rows = db.execute("SELECT id,record FROM jobs").fetchall()
        references = []
        for row in rows:
            job = json.loads(row["record"])
            request = job["request"]
            if any(request.get(key) == ident for key in ("source_asset_id", "mask_asset_id", "reference_asset_id")) or any(
                output.get("id") == ident for output in job.get("outputs", [])
            ):
                references.append(row["id"])
        return references

    def read_settings(self) -> dict[str, Any]:
        with self.connection() as db:
            return {row[0]: json.loads(row[1]) for row in db.execute("SELECT key,value FROM settings")}

    def save_settings(self, changes: dict):
        with self.connection() as db:
            db.executemany("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [
                (key, json.dumps(value)) for key, value in changes.items()
            ])

    def recover(self):
        """Never auto-retry an interrupted remote render: it may still be running."""
        with self.connection() as db:
            rows = db.execute("SELECT record FROM jobs WHERE status='running'").fetchall()
            for row in rows:
                job = json.loads(row[0])
                self.update_job(job["id"], {
                    "status": "failed", "stage": "Interrupted by server restart",
                    "error": "The studio restarted during this render. Check the compute provider before retrying; a remote job may still be running.",
                })

    def claim_next(self) -> dict | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            job = json.loads(row[0])
            job.update(status="running", stage="Preparing render", updated_at=now())
            db.execute("UPDATE jobs SET status=?,updated_at=?,record=? WHERE id=?", (
                job["status"], job["updated_at"], json.dumps(job), job["id"]
            ))
            return job
