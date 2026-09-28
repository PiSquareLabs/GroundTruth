"""Responsible-AI checks: near-duplicates and missing / inconsistent metadata."""
from __future__ import annotations

from datetime import datetime

import numpy as np

from gt import config


def cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def find_duplicates(assets: list[dict], threshold: float | None = None) -> list[tuple[str, str, float]]:
    """Pairs of assets whose embeddings are at least `threshold` similar."""
    threshold = config.DUPLICATE_THRESHOLD if threshold is None else threshold
    items = [(a["id"], a["embedding"]) for a in assets if a.get("embedding")]
    if len(items) < 2:
        return []
    ids = [i for i, _ in items]
    m = np.asarray([e for _, e in items], dtype=float)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1
    m = m / norms
    sims = m @ m.T
    out = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if sims[i, j] >= threshold:
                out.append((ids[i], ids[j], round(float(sims[i, j]), 4)))
    return out


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def metadata_flags(a: dict) -> list[str]:
    flags = []
    if a.get("lat") is None or a.get("lng") is None:
        flags.append("No GPS")
    cap, up = _dt(a.get("captured_at")), _dt(a.get("uploaded_at"))
    if cap is None:
        flags.append("No capture date")
    elif up and cap > up:
        flags.append("Capture date after upload date")
    if a.get("people_present"):
        flags.append("May contain people")
    if a.get("needs_review"):
        flags.append("AI output needs review")
    return flags
