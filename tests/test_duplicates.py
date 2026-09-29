import io

import numpy as np
from PIL import Image

from gt.trust import dhash, find_duplicates, metadata_flags


def _img(seed: int, noise: float = 0.0) -> io.BytesIO:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, (64, 64, 3)).astype(float)
    base = base + np.random.default_rng(99).normal(0, noise, base.shape)
    b = io.BytesIO()
    Image.fromarray(np.clip(base, 0, 255).astype("uint8")).resize((256, 256)).save(b, "JPEG", quality=70)
    b.seek(0)
    return b


def test_pixel_hash_catches_recompressed_copy_but_not_different_image():
    a = {"id": "a", "dhash": dhash(_img(1))}
    a_copy = {"id": "a_copy", "dhash": dhash(_img(1, noise=4))}
    other = {"id": "other", "dhash": dhash(_img(2))}
    dupes = find_duplicates([a, a_copy, other], max_bits=32)
    assert [(x, y, how) for x, y, _, how in dupes] == [("a", "a_copy", "pixel hash")]


def test_pixel_hash_overrides_similar_captions():
    # different pixels, near-identical caption embeddings -> not a duplicate when both are hashed
    a = {"id": "a", "dhash": dhash(_img(1)), "embedding": [1.0, 0.0]}
    b = {"id": "b", "dhash": dhash(_img(2)), "embedding": [0.999, 0.01]}
    assert find_duplicates([a, b], threshold=0.97, max_bits=32) == []


def test_near_duplicates_detected():
    assets = [
        {"id": "a", "embedding": [1.0, 0.0, 0.0]},
        {"id": "b", "embedding": [0.999, 0.01, 0.0]},
        {"id": "c", "embedding": [0.0, 1.0, 0.0]},
        {"id": "d", "embedding": None},
    ]
    dupes = find_duplicates(assets, threshold=0.97)
    assert [(x, y, how) for x, y, _, how in dupes] == [("a", "b", "embedding")]


def test_no_duplicates_below_threshold():
    assets = [{"id": "a", "embedding": [1.0, 0.0]}, {"id": "b", "embedding": [0.7, 0.7]}]
    assert find_duplicates(assets, threshold=0.97) == []


def test_metadata_flags():
    a = {"lat": None, "lng": None, "captured_at": "2026-07-02T00:00:00", "uploaded_at": "2026-07-01T00:00:00Z"}
    flags = metadata_flags(a)
    assert "No GPS" in flags and "Capture date after upload date" in flags
