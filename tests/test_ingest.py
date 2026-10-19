from advocacy_intel.ingestion.extract import UnitLabels, Usage
from advocacy_intel.ingestion.ingest import coverage_markdown, process_document
from advocacy_intel.ingestion.text_checks import PageText

ROW = {
    "date": "2018-04-20",
    "title": "A Report",
    "document_type": "report",
    "source_url": "https://www.hrw.org/report/x",
}
RAW = [
    PageText(
        1,
        "Recommendations\nTo the Government\n•(cid:3) Halt expulsions.\n"
        "•(cid:3) Allow UNHCR access.\nAcknowledgments",
    )
]


def fake(system, user):
    return UnitLabels(action_requested="Halt it", topic=["expulsion"]), Usage(7, 3)


def test_records_carry_verbatim_text_provenance_and_labels():
    r = process_document("doc", ROW, RAW, fake)
    assert r.ok
    rec = r.records[0]
    assert rec.recommendation_text == "Halt expulsions."
    assert rec.target_actor_raw == "To the Government"
    assert rec.target_actor is None and rec.geography == []  # not model-touched (D38)
    assert (rec.source_page, rec.cleaning_version) == (1, "clean-v1")
    assert rec.action_requested == "Halt it" and rec.extraction == "extract_unit_v1 / chat"
    assert r.usage == Usage(14, 6)


def test_a_labelling_failure_keeps_the_record_and_fails_the_run():
    def boom(system, user):
        raise TimeoutError("slow")

    r = process_document("doc", ROW, RAW, boom)
    assert len(r.records) == 2 and r.records[0].action_requested is None
    assert not r.ok and len(r.label_failures) == 2


def test_no_section_fails_the_run():
    r = process_document("doc", ROW, [PageText(1, "Just prose here.")], None)
    assert not r.ok and r.records == []
    assert "no recommendations section found" in coverage_markdown([r])


def test_no_model_mode_gives_unlabelled_records():
    r = process_document("doc", ROW, RAW, None)
    assert r.ok and r.records[0].extraction is None
