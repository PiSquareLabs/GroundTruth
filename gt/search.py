"""Semantic search (query embedding + cosine) with a keyword/tag fallback. Each hit explains why it matched."""
from __future__ import annotations

import re

from gt.trust import cosine

STOP = {"a", "an", "the", "of", "in", "on", "with", "and", "or", "to", "for", "at", "by", "is", "are", "photo", "image", "show", "me"}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP and len(t) > 1}


def _fields(a: dict) -> dict[str, set[str]]:
    return {
        "caption": tokens(a.get("caption") or ""),
        "tags": tokens(" ".join(a.get("tags") or [])),
        "signals": tokens(" ".join(s.replace("_", " ") for s in a.get("signals") or [])),
        "activity": tokens((a.get("activity_type") or "").replace("_", " ")),
        "project": tokens(a.get("project_name") or ""),
    }


def _matched_terms(q: set[str], a: dict) -> dict[str, list[str]]:
    out = {}
    for field, toks in _fields(a).items():
        hit = sorted(q & toks | {t for t in q for w in toks if len(t) > 3 and (w.startswith(t) or t.startswith(w))})
        if hit:
            out[field] = hit
    return out


def _why(matched: dict[str, list[str]]) -> str:
    return "; ".join(f"{f}: {', '.join(v)}" for f, v in matched.items())


def keyword_search(query: str, assets: list[dict], top_k: int = 24) -> list[dict]:
    q = tokens(query)
    weights = {"tags": 2.0, "signals": 2.0, "activity": 1.5, "caption": 1.0, "project": 1.0}
    hits = []
    for a in assets:
        m = _matched_terms(q, a)
        if not m:
            continue
        # each query word counts once, by the most specific field it matched; score = weighted coverage
        best = {t: max(weights[f] for f, v in m.items() if t in v) for t in {t for v in m.values() for t in v}}
        s = sum(best.values()) / (max(weights.values()) * max(len(q), 1))
        hits.append({"asset": a, "score": s, "why": "keyword match — " + _why(m)})
    return sorted(hits, key=lambda h: -h["score"])[:top_k]


def semantic_search(query_emb: list[float], query: str, assets: list[dict], top_k: int = 24,
                    min_sim: float = 0.6, rel_window: float = 0.15) -> list[dict]:
    """Keep hits with cosine >= min_sim and within rel_window of the best hit (tuned on gemini-embedding-001)."""
    q = tokens(query)
    hits = []
    for a in assets:
        emb = a.get("embedding")
        if not emb or len(emb) != len(query_emb):
            continue
        s = cosine(query_emb, emb)
        if s < min_sim:
            continue
        m = _matched_terms(q, a)
        why = f"meaning similarity {s:.2f}"
        why += f"; shared terms — {_why(m)}" if m else "; no shared words (matched on meaning of caption/tags)"
        hits.append({"asset": a, "score": s, "why": why})
    hits.sort(key=lambda h: -h["score"])
    if hits:
        hits = [h for h in hits if h["score"] >= hits[0]["score"] - rel_window]
    return hits[:top_k]
