import sqlite3
import time
from contextlib import contextmanager

from app import config

DB_PATH = None  # set by init_db()


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    # DB file lives under the assessment engine's output/ folder, which is already
    # git-ignored, so no separate ignore entry is needed for it.
    global DB_PATH
    import os
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    DB_PATH = db_path or str(config.OUTPUT_DIR / "backend_runs.db")
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                assessment_url TEXT NOT NULL,
                headless INTEGER NOT NULL,
                test_account_label TEXT NOT NULL,
                model TEXT NOT NULL,
                max_retries INTEGER NOT NULL,
                output_dir TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
        """)


def create_run(run_id, assessment_url, headless, test_account_label, model, max_retries, output_dir):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO runs (id, assessment_url, headless, test_account_label, model, "
            "max_retries, output_dir, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)",
            (run_id, assessment_url, int(headless), test_account_label, model, max_retries, output_dir, time.time()),
        )


def update_run(run_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))


def get_run(run_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def list_runs(limit=50):
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def queue_position(run_id):
    # 1-indexed position among still-queued runs, counting a currently-running run (if any)
    # as occupying the front of the line. Returns None once the run is no longer queued.
    run = get_run(run_id)
    if not run or run["status"] != "queued":
        return None
    with _conn() as conn:
        ahead = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE status = 'queued' AND created_at < ?",
            (run["created_at"],),
        ).fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM runs WHERE status = 'running'").fetchone()[0]
    return ahead + running + 1
