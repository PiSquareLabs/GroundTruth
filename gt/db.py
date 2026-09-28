"""SQLite data layer (plain sqlite3). JSON columns are stored as TEXT and decoded on read."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable

from gt import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    location_name TEXT
);
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    filename TEXT,
    public_id TEXT,
    url TEXT,
    local_path TEXT,
    width INTEGER,
    height INTEGER,
    bytes INTEGER,
    format TEXT,
    captured_at TEXT,
    uploaded_at TEXT,
    lat REAL,
    lng REAL,
    exif_json TEXT,
    source TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id),
    caption TEXT,
    activity_type TEXT,
    tags TEXT,
    signals TEXT,
    people_present INTEGER DEFAULT 0,
    embedding TEXT,
    model TEXT,
    raw_output TEXT,
    needs_review INTEGER DEFAULT 0,
    analyzed_at TEXT
);
CREATE TABLE IF NOT EXISTS pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    before_id TEXT REFERENCES assets(id),
    after_id TEXT REFERENCES assets(id),
    score REAL,
    breakdown TEXT,
    status TEXT DEFAULT 'suggested',
    reviewed_at TEXT,
    UNIQUE(before_id, after_id)
);
CREATE TABLE IF NOT EXISTS transform_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT REFERENCES assets(id),
    purpose TEXT,
    transformation TEXT,
    url TEXT,
    created_at TEXT,
    UNIQUE(asset_id, purpose, transformation)
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

JSON_COLS = {"tags", "signals", "embedding", "breakdown", "exif_json"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_schema() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def reset() -> None:
    with conn() as c:
        c.executescript(
            "DROP TABLE IF EXISTS transform_log; DROP TABLE IF EXISTS pairs;"
            "DROP TABLE IF EXISTS analyses; DROP TABLE IF EXISTS assets;"
            "DROP TABLE IF EXISTS projects; DROP TABLE IF EXISTS meta;"
        )
    init_schema()


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_COLS & d.keys():
        if isinstance(d[k], str) and d[k]:
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def _encode(v: Any) -> Any:
    return json.dumps(v) if isinstance(v, (dict, list)) else v


def query(sql: str, params: Iterable = ()) -> list[dict]:
    with conn() as c:
        return [_decode(r) for r in c.execute(sql, tuple(params)).fetchall()]


def query_one(sql: str, params: Iterable = ()) -> dict | None:
    with conn() as c:
        return _decode(c.execute(sql, tuple(params)).fetchone())


def upsert(table: str, row: dict, conflict: str = "id") -> None:
    cols = list(row)
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{k}=excluded.{k}" for k in cols if k not in conflict.split(","))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    sql += f" ON CONFLICT({conflict}) DO UPDATE SET {updates}" if updates else " ON CONFLICT DO NOTHING"
    with conn() as c:
        c.execute(sql, [_encode(row[k]) for k in cols])


def get_meta(key: str) -> str | None:
    r = query_one("SELECT value FROM meta WHERE key=?", (key,))
    return r["value"] if r else None


def set_meta(key: str, value: str) -> None:
    upsert("meta", {"key": key, "value": value}, conflict="key")


# --- domain queries ---------------------------------------------------------------

ASSET_SELECT = """
SELECT a.*, p.name AS project_name,
       an.caption, an.activity_type, an.tags, an.signals, an.people_present,
       an.embedding, an.model, an.raw_output, an.needs_review, an.analyzed_at
FROM assets a
LEFT JOIN projects p ON p.id = a.project_id
LEFT JOIN analyses an ON an.asset_id = a.id
"""


def projects() -> list[dict]:
    return query(
        "SELECT p.*, COUNT(a.id) AS asset_count FROM projects p "
        "LEFT JOIN assets a ON a.project_id = p.id GROUP BY p.id ORDER BY p.name"
    )


def assets(project_id: str | None = None) -> list[dict]:
    if project_id:
        return query(ASSET_SELECT + " WHERE a.project_id=? ORDER BY a.captured_at", (project_id,))
    return query(ASSET_SELECT + " ORDER BY a.captured_at")


def asset(asset_id: str) -> dict | None:
    return query_one(ASSET_SELECT + " WHERE a.id=?", (asset_id,))


def pairs(status: str | None = None) -> list[dict]:
    if status:
        return query("SELECT * FROM pairs WHERE status=? ORDER BY score DESC", (status,))
    return query("SELECT * FROM pairs ORDER BY score DESC")


def set_pair_status(pair_id: int, status: str) -> None:
    with conn() as c:
        c.execute("UPDATE pairs SET status=?, reviewed_at=? WHERE id=?", (status, now_iso(), pair_id))


def log_transform(asset_id: str, purpose: str, transformation: str, url: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO transform_log (asset_id, purpose, transformation, url, created_at)"
            " VALUES (?,?,?,?,?)",
            (asset_id, purpose, transformation, url, now_iso()),
        )


def transforms(asset_id: str) -> list[dict]:
    return query("SELECT * FROM transform_log WHERE asset_id=? ORDER BY id", (asset_id,))
