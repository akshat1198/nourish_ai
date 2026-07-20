"""TheMealDB step parsing — strip 'STEP N' marker pollution (surfaced by 7.1).

Pure functions, no DB. Guards the fix for the 6.2c ingest that kept standalone
"STEP 1/2/3" delimiter lines as their own steps.
"""
from scripts.ingest.themealdb import clean_steps, parse_instructions


def test_parse_drops_standalone_marker_lines():
    raw = "STEP 1\r\nHeat the oil.\r\nSTEP 2\r\nAdd the onions."
    assert parse_instructions(raw) == ["Heat the oil.", "Add the onions."]


def test_parse_strips_inline_marker_prefix():
    raw = "Step 1: Heat the oil.\nStep 2. Add the onions."
    assert parse_instructions(raw) == ["Heat the oil.", "Add the onions."]


def test_clean_steps_is_idempotent_on_stored_rows():
    stored = ["step 1", "Heat the oil.", "step 2", "Add the onions."]
    cleaned = clean_steps(stored)
    assert cleaned == ["Heat the oil.", "Add the onions."]
    assert clean_steps(cleaned) == cleaned  # re-running changes nothing


def test_genuine_step_starting_with_step_word_is_kept():
    # No delimiter after the number => not a marker; leave it alone.
    assert clean_steps(["Step 1 minute of resting helps."]) == [
        "Step 1 minute of resting helps."
    ]


def test_clean_ordinary_steps_unchanged():
    steps = ["Boil the pasta.", "Drain and serve."]
    assert clean_steps(steps) == steps
