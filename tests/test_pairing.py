import pytest

from gt.pairing import haversine_m, score_pair, suggest

W = {"location": 0.4, "visual": 0.4, "time": 0.2}


def asset(id, lat=12.97, lng=77.59, t="2026-06-01T09:00:00", emb=(1.0, 0.0), act="drain_cleaning", project="p1"):
    return {"id": id, "lat": lat, "lng": lng, "captured_at": t, "embedding": list(emb),
            "activity_type": act, "project_id": project}


def test_perfect_pair_scores_one():
    s, bd = score_pair(asset("a"), asset("b", t="2026-06-20T09:00:00"), W)
    assert s == pytest.approx(1.0)
    assert bd["location"]["value"] == 1.0 and bd["time"]["value"] == 1.0


def test_weights_are_applied():
    # same place, orthogonal embeddings, correct order -> 0.4*1 + 0.4*0 + 0.2*1
    s, _ = score_pair(asset("a"), asset("b", t="2026-06-20T09:00:00", emb=(0.0, 1.0)), W)
    assert s == pytest.approx(0.6)


def test_reversed_time_gets_zero_time_score():
    _, bd = score_pair(asset("a", t="2026-07-01T00:00:00"), asset("b", t="2026-06-01T00:00:00"), W)
    assert bd["time"]["value"] == 0.0


def test_distance_reduces_location_score():
    near, _ = score_pair(asset("a"), asset("b", t="2026-06-20T09:00:00"), W)
    far, bd = score_pair(asset("a"), asset("b", lat=13.07, t="2026-06-20T09:00:00"), W)
    assert far < near and bd["location"]["value"] < 0.01


def test_missing_gps_same_project_is_neutral():
    _, bd = score_pair(asset("a", lat=None, lng=None), asset("b", t="2026-06-20T09:00:00"), W)
    assert bd["location"]["value"] == 0.5


def test_haversine_known_distance():
    assert haversine_m(0, 0, 0, 1) == pytest.approx(111_195, rel=1e-3)


def test_suggest_orders_by_time_and_skips_other_activities():
    later = asset("later", t="2026-06-20T09:00:00")
    earlier = asset("earlier")
    other = asset("trees", act="tree_planting")
    out = suggest([later, earlier, other], min_score=0.5)
    assert len(out) == 1
    assert out[0]["before_id"] == "earlier" and out[0]["after_id"] == "later"


def test_suggest_never_pairs_across_projects():
    a = asset("a", project="p1")
    b = asset("b", t="2026-06-20T09:00:00", project="p2")
    assert suggest([a, b], min_score=0.0) == []
