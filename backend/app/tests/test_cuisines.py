"""Cuisine taxonomy matching — pure, no DB."""
from app.core.cuisines import VALID_CUISINE_IDS, cuisine_matches, parse_cuisine_id


def test_parse_cuisine_id():
    assert parse_cuisine_id("indian") == ("indian", None)
    assert parse_cuisine_id("indian/gujarati") == ("indian", "gujarati")


def test_top_level_matches_any_region():
    assert cuisine_matches("indian", "gujarati", ["indian"])
    assert cuisine_matches("indian", None, ["indian"])


def test_child_requires_matching_region():
    assert cuisine_matches("indian", "gujarati", ["indian/gujarati"])
    assert not cuisine_matches("indian", "punjabi", ["indian/gujarati"])
    assert not cuisine_matches("indian", None, ["indian/gujarati"])


def test_or_semantics_across_selection():
    assert cuisine_matches("italian", None, ["asian", "italian"])
    assert not cuisine_matches("mexican", None, ["asian", "italian"])


def test_empty_selection_matches_all():
    assert cuisine_matches("italian", None, [])
    assert cuisine_matches(None, None, [])


def test_null_cuisine_never_matches_a_selection():
    assert not cuisine_matches(None, None, ["italian"])


def test_valid_ids_membership():
    assert "indian" in VALID_CUISINE_IDS
    assert "indian/gujarati" in VALID_CUISINE_IDS
    assert "asian/chinese" in VALID_CUISINE_IDS
    assert "indian/atlantis" not in VALID_CUISINE_IDS


def test_frontend_cuisine_ids_match_backend():
    """frontend/lib/cuisines.ts ids must equal backend VALID_CUISINE_IDS (they
    can't share a module across the Python/TS split — guard the drift)."""
    import re
    from pathlib import Path

    fe = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "cuisines.ts"
    ids = set(re.findall(r'id:\s*"([^"]+)"', fe.read_text()))
    assert ids == VALID_CUISINE_IDS, {
        "frontend_only": ids - VALID_CUISINE_IDS,
        "backend_only": VALID_CUISINE_IDS - ids,
    }
