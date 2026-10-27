import re

from backend.app.patterns import load_patterns, patterns_for_prompt

REQUIRED = {"id", "name", "category", "description", "signals", "what_next", "advice"}


def test_patterns_are_well_formed():
    data = load_patterns()
    ids = [p["id"] for p in data["patterns"]]
    assert len(ids) == len(set(ids)), "pattern ids must be unique"
    for p in data["patterns"]:
        assert REQUIRED <= p.keys(), p["id"]
        assert p["signals"] and p["advice"], p["id"]


def test_no_personal_data_leaked():
    raw = str(load_patterns())
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", raw), "no email addresses"
    assert not re.search(r"\+?\d[\d\s-]{8,}\d", raw), "no phone numbers"


def test_prompt_summary_mentions_every_pattern():
    text = patterns_for_prompt()
    for p in load_patterns()["patterns"]:
        assert p["id"] in text
