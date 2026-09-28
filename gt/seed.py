"""Load seed/analysis.json into SQLite.

Demo mode: the DB is rebuilt whenever the seed file changes (the seed is the source of truth).
Live mode: the seed is imported once into an empty DB; later uploads are added on top.
"""
from __future__ import annotations

import hashlib
import json

from gt import config, db

EMPTY_SEED = {"version": 1, "cloud_name": None, "projects": [], "assets": [], "pairs": [], "transforms": [], "report": None}


def read_seed() -> dict:
    if not config.SEED_FILE.exists():
        return dict(EMPTY_SEED)
    data = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))
    return {**EMPTY_SEED, **data}


def write_seed(data: dict) -> None:
    config.SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SEED_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_hash() -> str:
    if not config.SEED_FILE.exists():
        return "none"
    return hashlib.sha256(config.SEED_FILE.read_bytes()).hexdigest()[:16]


def load_into_db(data: dict) -> None:
    for p in data["projects"]:
        db.upsert("projects", {k: p.get(k) for k in ("id", "name", "description", "location_name")})

    for a in data["assets"]:
        local = config.SEED_IMAGES / a["filename"] if a.get("filename") else None
        db.upsert(
            "assets",
            {
                "id": a["id"],
                "project_id": a.get("project_id"),
                "filename": a.get("filename"),
                "public_id": a.get("public_id"),
                "url": a.get("url"),
                "local_path": str(local) if local and local.exists() else None,
                "width": a.get("width"),
                "height": a.get("height"),
                "bytes": a.get("bytes"),
                "format": a.get("format"),
                "captured_at": a.get("captured_at"),
                "uploaded_at": a.get("uploaded_at"),
                "lat": a.get("lat"),
                "lng": a.get("lng"),
                "exif_json": a.get("exif") or {},
                "source": a.get("source", "seed"),
            },
        )
        an = a.get("analysis")
        if an:
            db.upsert(
                "analyses",
                {
                    "asset_id": a["id"],
                    "caption": an.get("caption"),
                    "activity_type": an.get("activity_type"),
                    "tags": an.get("tags") or [],
                    "signals": an.get("signals") or [],
                    "people_present": int(bool(an.get("people_present"))),
                    "embedding": an.get("embedding"),
                    "model": an.get("model"),
                    "raw_output": an.get("raw_output"),
                    "needs_review": int(bool(an.get("needs_review"))),
                    "analyzed_at": an.get("analyzed_at"),
                },
                conflict="asset_id",
            )

    for p in data["pairs"]:
        db.upsert(
            "pairs",
            {
                "before_id": p["before_id"],
                "after_id": p["after_id"],
                "score": p.get("score"),
                "breakdown": p.get("breakdown") or {},
                "status": p.get("status", "suggested"),
                "reviewed_at": p.get("reviewed_at"),
            },
            conflict="before_id,after_id",
        )

    for t in data["transforms"]:
        db.log_transform(t["asset_id"], t["purpose"], t["transformation"], t["url"])

    if data.get("report"):
        db.set_meta("report", json.dumps(data["report"]))
    if data.get("cloud_name"):
        db.set_meta("cloud_name", data["cloud_name"])


def ensure_loaded() -> str:
    """Make sure the DB reflects the seed. Returns a short status string."""
    db.init_schema()
    h = _seed_hash()
    if config.DEMO_MODE:
        if db.get_meta("seed_hash") != h:
            db.reset()
            load_into_db(read_seed())
            db.set_meta("seed_hash", h)
            return "rebuilt from seed"
        return "seed up to date"
    if not db.query_one("SELECT id FROM assets LIMIT 1"):
        load_into_db(read_seed())
        db.set_meta("seed_hash", h)
        return "seed imported"
    return "live database"
