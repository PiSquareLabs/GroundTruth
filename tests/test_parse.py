from gt.analysis import parse

GOOD = '{"caption": "A clogged drain with plastic litter.", "activity_type": "drain_cleaning", ' \
       '"signals": ["clogged_drain", "litter", "made_up"], "tags": ["Drain", "plastic"], "people_present": false}'


def test_valid_json_parses():
    an, ok = parse(GOOD)
    assert ok and not an["needs_review"]
    assert an["activity_type"] == "drain_cleaning"
    assert an["signals"] == ["clogged_drain", "litter"]  # unknown signal dropped
    assert an["tags"] == ["drain", "plastic"]


def test_code_fenced_json_parses():
    an, ok = parse("```json\n" + GOOD + "\n```")
    assert ok and an["caption"].startswith("A clogged drain")


def test_unknown_activity_becomes_other():
    an, ok = parse('{"caption": "x", "activity_type": "painting", "signals": [], "tags": [], "people_present": true}')
    assert ok and an["activity_type"] == "other" and an["people_present"] is True


def test_garbage_falls_back_to_needs_review():
    for raw in ["not json at all", "", "[1, 2]", '{"activity_type": "road_repair"}', None]:
        an, ok = parse(raw)
        assert not ok and an["needs_review"] and an["caption"] is None


def test_report_citation_check_finds_unknown_ids():
    from gt.report import cited_ids, unknown_citations
    text = "Bare soil [a-before-01, a-before-102] then saplings [a-after-01]."
    assert cited_ids(text) == {"a-before-01", "a-before-102", "a-after-01"}
    assert unknown_citations(text, {"a-before-01", "a-after-01"}) == ["a-before-102"]
