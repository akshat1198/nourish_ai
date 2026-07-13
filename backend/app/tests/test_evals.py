"""Guard: the eval harness runs and the SQL path never violates hard constraints."""
from app.evals.common import QUERIES_PATH, load_cases
from app.evals.run_retrieval import run
from app.tests.conftest import requires_db


def test_eval_cases_load():
    cases = load_cases()
    assert len(cases) >= 30
    assert all(c.relevant_titles for c in cases)


@requires_db
def test_sql_path_has_zero_constraint_violations_and_resolves_gold():
    metrics = run(mode="sql", cases_path=QUERIES_PATH)
    assert not metrics.missing_gold, f"unresolved gold titles: {metrics.missing_gold}"
    # SQL retrieval enforces filters, so returned results must never violate them.
    assert metrics.constraint_violations == 0
    # Sanity floor (Risk 2 tripwire is hit@5 < 0.6); the structured baseline is 1.0.
    assert metrics.summary()["hit@10"] >= 0.9
