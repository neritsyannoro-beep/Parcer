"""SQLite-хранилище: дедупликация между запусками и история скоров.

Зачем БД, если лента — статический JSON:
  * помнить, что уже показывали (метка «новое» в интерфейсе);
  * знать снимок списка монет, чтобы вычислять новые листинги;
  * видеть, растёт ли сюжет от запуска к запуску.

Схема намеренно плоская — при переезде на Postgres/Supabase меняется только
этот файл.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    source        TEXT,
    tier          INTEGER,
    kind          TEXT,
    published     TEXT,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    best_score    REAL DEFAULT 0,
    last_score    REAL DEFAULT 0,
    runs          INTEGER DEFAULT 1,
    tags          TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_items_first_seen ON items(first_seen);
CREATE INDEX IF NOT EXISTS idx_items_score ON items(best_score);

CREATE TABLE IF NOT EXISTS kv (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started     TEXT NOT NULL,
    fetched     INTEGER,
    published   INTEGER,
    hot         INTEGER,
    duration_s  REAL
);
"""


@contextmanager
def connect(db_path: Path | None = None):
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_seen_ids(conn: sqlite3.Connection) -> dict[str, dict]:
    """id -> {first_seen, best_score, runs} для всех известных записей."""
    rows = conn.execute(
        "SELECT id, first_seen, best_score, runs FROM items"
    ).fetchall()
    return {
        r["id"]: {
            "first_seen": r["first_seen"],
            "best_score": r["best_score"],
            "runs": r["runs"],
        }
        for r in rows
    }


def upsert_items(conn: sqlite3.Connection, items: list[dict]) -> None:
    now = _now()
    for it in items:
        conn.execute(
            """
            INSERT INTO items (id, title, url, source, tier, kind, published,
                               first_seen, last_seen, best_score, last_score, runs, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen  = excluded.last_seen,
                last_score = excluded.last_score,
                best_score = MAX(items.best_score, excluded.last_score),
                runs       = items.runs + 1,
                tags       = excluded.tags
            """,
            (
                it["id"], it["title"], it["url"], it.get("source"), it.get("tier"),
                it.get("kind"), it.get("published"), now, now,
                it.get("score", 0), it.get("score", 0),
                json.dumps(it.get("tags", []), ensure_ascii=False),
            ),
        )


def get_kv(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def set_kv(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        """INSERT INTO kv (key, value, updated) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated = excluded.updated""",
        (key, json.dumps(value, ensure_ascii=False), _now()),
    )


def get_coin_snapshot(conn: sqlite3.Connection) -> set[str]:
    return set(get_kv(conn, "coingecko_coin_ids", []) or [])


def save_coin_snapshot(conn: sqlite3.Connection, ids: set[str]) -> None:
    # Снимок большой (~15k id), поэтому храним одной записью в kv.
    set_kv(conn, "coingecko_coin_ids", sorted(ids))


def record_run(
    conn: sqlite3.Connection, fetched: int, published: int, hot: int, duration_s: float
) -> None:
    conn.execute(
        "INSERT INTO runs (started, fetched, published, hot, duration_s) VALUES (?, ?, ?, ?, ?)",
        (_now(), fetched, published, hot, round(duration_s, 2)),
    )


def prune(conn: sqlite3.Connection) -> int:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=config.HISTORY_RETENTION_DAYS)
    ).isoformat()
    cur = conn.execute("DELETE FROM items WHERE first_seen < ?", (cutoff,))
    conn.execute("DELETE FROM runs WHERE started < ?", (cutoff,))
    return cur.rowcount
