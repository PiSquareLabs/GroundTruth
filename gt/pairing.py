"""Before/after pair suggestion.

score = w_location * location_proximity + w_visual * visual_similarity + w_time * time_ordering
(weights in gt/config.py). Suggestions are never auto-confirmed; a person confirms or rejects.
"""
from __future__ import annotations

import math
from datetime import datetime
from itertools import combinations

from gt import config, db
from gt.trust import cosine


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def location_proximity(a: dict, b: dict, scale_m: float | None = None) -> tuple[float, str]:
    scale_m = scale_m or config.LOCATION_SCALE_M
    if None not in (a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng")):
        d = haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])
        return 1 / (1 + (d / scale_m) ** 2), f"{d:.0f} m apart"
    if a.get("project_id") and a.get("project_id") == b.get("project_id"):
        return 0.5, "GPS missing; same project"
    return 0.0, "GPS missing"


def visual_similarity(a: dict, b: dict) -> tuple[float, str]:
    if a.get("embedding") and b.get("embedding"):
        s = max(0.0, cosine(a["embedding"], b["embedding"]))
        return s, f"embedding cosine {s:.2f}"
    return 0.0, "no embedding"


def _dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None) if s else None
    except ValueError:
        return None


def time_ordering(before: dict, after: dict) -> tuple[float, str]:
    tb, ta = _dt(before.get("captured_at")), _dt(after.get("captured_at"))
    if tb is None or ta is None:
        return 0.5, "capture date missing"
    if ta > tb:
        return 1.0, f"after is {(ta - tb).days} days later"
    return 0.0, "after is not later than before"


def score_pair(before: dict, after: dict, weights: dict | None = None) -> tuple[float, dict]:
    w = weights or config.PAIR_WEIGHTS
    loc, loc_n = location_proximity(before, after)
    vis, vis_n = visual_similarity(before, after)
    tim, tim_n = time_ordering(before, after)
    total = w["location"] * loc + w["visual"] * vis + w["time"] * tim
    breakdown = {
        "location": {"value": round(loc, 3), "weight": w["location"], "note": loc_n},
        "visual": {"value": round(vis, 3), "weight": w["visual"], "note": vis_n},
        "time": {"value": round(tim, 3), "weight": w["time"], "note": tim_n},
    }
    return round(total, 4), breakdown


def order(a: dict, b: dict) -> tuple[dict, dict]:
    """Earlier capture is 'before'. Undated images keep id order."""
    ta, tb = _dt(a.get("captured_at")), _dt(b.get("captured_at"))
    if ta and tb and tb < ta:
        return b, a
    return a, b


def suggest(assets: list[dict], min_score: float | None = None) -> list[dict]:
    """Score candidate pairs that share an activity type; keep those above min_score."""
    min_score = config.PAIR_MIN_SCORE if min_score is None else min_score
    out = []
    for x, y in combinations(assets, 2):
        if not x.get("activity_type") or x.get("activity_type") != y.get("activity_type"):
            continue
        before, after = order(x, y)
        s, bd = score_pair(before, after)
        if s >= min_score:
            out.append({"before_id": before["id"], "after_id": after["id"], "score": s, "breakdown": bd})
    return sorted(out, key=lambda p: -p["score"])


def save_suggestions(suggestions: list[dict]) -> int:
    """Insert new suggestions; existing pairs keep their review status."""
    with db.conn() as c:
        for p in suggestions:
            c.execute(
                "INSERT INTO pairs (before_id, after_id, score, breakdown, status) VALUES (?,?,?,?, 'suggested')"
                " ON CONFLICT(before_id, after_id) DO UPDATE SET score=excluded.score, breakdown=excluded.breakdown",
                (p["before_id"], p["after_id"], p["score"], db._encode(p["breakdown"])),
            )
    return len(suggestions)
