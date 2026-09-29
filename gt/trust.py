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


HASH_SIZE = 16  # 16x16 difference hash = 256 bits


def dhash(fp) -> str:
    """Perceptual difference hash of the pixels (robust to re-encoding / resizing). Returns hex."""
    from PIL import Image, ImageOps

    with Image.open(fp) as im:
        im = ImageOps.exif_transpose(im).convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
        a = np.asarray(im, dtype=int)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):0{HASH_SIZE * HASH_SIZE // 4}x}"


def hamming(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def find_duplicates(assets: list[dict], threshold: float | None = None,
                    max_bits: int | None = None) -> list[tuple[str, str, float, str]]:
    """Near-duplicate pairs as (id1, id2, similarity 0-1, method).

    Uses the pixel perceptual hash when both images have one (<= max_bits differing bits);
    otherwise falls back to caption/tag embedding cosine >= threshold.
    """
    threshold = config.DUPLICATE_THRESHOLD if threshold is None else threshold
    max_bits = config.DUPLICATE_HASH_BITS if max_bits is None else max_bits
    out = []
    hashed = [a for a in assets if a.get("dhash")]
    for i in range(len(hashed)):
        for j in range(i + 1, len(hashed)):
            d = hamming(hashed[i]["dhash"], hashed[j]["dhash"])
            if d <= max_bits:
                out.append((hashed[i]["id"], hashed[j]["id"], round(1 - d / HASH_SIZE ** 2, 4), "pixel hash"))
    hashed_ids = {a["id"] for a in hashed}
    items = [(a["id"], a["embedding"]) for a in assets if a.get("embedding")]
    if len(items) < 2:
        return out
    ids = [i for i, _ in items]
    m = np.asarray([e for _, e in items], dtype=float)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1
    m = m / norms
    sims = m @ m.T
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if ids[i] in hashed_ids and ids[j] in hashed_ids:
                continue  # pixel hash already decided for this pair
            if sims[i, j] >= threshold:
                out.append((ids[i], ids[j], round(float(sims[i, j]), 4), "embedding"))
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
