from advocacy_intel.evaluation.gold_check import Item, compare, normalise, report_markdown


def gold(key, text, page=1, actor="To A"):
    return Item(key, text, page, actor)


def test_normalise_ignores_case_spacing_punctuation_and_footnote_digits():
    assert normalise("Halt  the practice.12") == normalise("halt the practice")


def test_identical_lists_give_full_recall_and_precision():
    g = [gold("r01", "Halt expulsions now."), gold("r02", "Allow UNHCR access.")]
    r = [gold("u1", "Allow UNHCR access."), gold("u2", "Halt expulsions now.")]
    res = compare(g, r)
    assert (res.recall, res.precision) == (1.0, 1.0)
    assert {(p.gold.key, p.record.key) for p in res.matched} == {("r01", "u2"), ("r02", "u1")}


def test_missed_and_extra_are_reported_separately():
    g = [gold("r01", "Halt expulsions now."), gold("r02", "Ratify the 1951 Convention fully.")]
    r = [gold("u1", "Halt expulsions now."), gold("u2", "Publish detention lists weekly.")]
    res = compare(g, r)
    assert [x.key for x in res.missed_gold] == ["r02"]
    assert [x.key for x in res.extra_records] == ["u2"]
    assert (res.recall, res.precision) == (0.5, 0.5)


def test_two_bullets_merged_into_one_record_is_not_counted_as_a_match():
    a = "Halt all pullbacks and expulsions of refugees immediately."
    b = "Allow UNHCR to resume registering asylum seekers in the country."
    res = compare([gold("r01", a), gold("r02", b)], [gold("u1", a + " " + b)])
    assert res.matched == [] and len(res.missed_gold) == 2 and len(res.extra_records) == 1


def test_matching_is_one_to_one():
    t = "Halt expulsions now."
    res = compare([gold("r01", t), gold("r02", t)], [gold("u1", t)])
    assert len(res.matched) == 1 and len(res.missed_gold) == 1


def test_page_and_actor_differences_are_flagged_on_matched_pairs():
    t = "Halt expulsions now."
    res = compare(
        [gold("r01", t, page=95, actor="To  the Government")], [gold("u1", t, 96, "To the EU")]
    )
    assert len(res.page_mismatches) == 1 and len(res.actor_mismatches) == 1


def test_whitespace_only_actor_difference_is_not_a_mismatch():
    t = "Halt expulsions now."
    res = compare(
        [gold("r01", t, actor="To  the Government")], [gold("u1", t, actor="To the government")]
    )
    assert res.actor_mismatches == []


def test_near_match_is_listed_for_a_human_not_counted():
    g = "Ensure that every person can challenge the decision before an independent and impartial court."
    r = "Ensure that every person can challenge the decision before an independent court."
    res = compare([gold("r01", g)], [gold("u1", r)])
    assert res.matched == [] and len(res.near) == 1


def test_report_states_counts_not_only_percentages():
    res = compare([gold("r01", "Halt expulsions now.")], [gold("u1", "Halt expulsions now.")])
    md = report_markdown("doc", {"scope": "all", "labelled_by": "x"}, res)
    assert "1/1 = 100%" in md
