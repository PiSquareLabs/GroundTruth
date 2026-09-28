from gt.trust import find_duplicates, metadata_flags


def test_near_duplicates_detected():
    assets = [
        {"id": "a", "embedding": [1.0, 0.0, 0.0]},
        {"id": "b", "embedding": [0.999, 0.01, 0.0]},
        {"id": "c", "embedding": [0.0, 1.0, 0.0]},
        {"id": "d", "embedding": None},
    ]
    dupes = find_duplicates(assets, threshold=0.97)
    assert [(x, y) for x, y, _ in dupes] == [("a", "b")]


def test_no_duplicates_below_threshold():
    assets = [{"id": "a", "embedding": [1.0, 0.0]}, {"id": "b", "embedding": [0.7, 0.7]}]
    assert find_duplicates(assets, threshold=0.97) == []


def test_metadata_flags():
    a = {"lat": None, "lng": None, "captured_at": "2026-07-02T00:00:00", "uploaded_at": "2026-07-01T00:00:00Z"}
    flags = metadata_flags(a)
    assert "No GPS" in flags and "Capture date after upload date" in flags
