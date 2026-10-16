import pytest

from wl3.feedback.rocchio import Rocchio


def test_relevant_documents_increase_term_weights():
    rocchio = Rocchio()
    result = rocchio.update_query(
        {"ai": 1.0},
        [{"ai": 2.0, "robotics": 1.0}],
    )

    assert result["ai"] == pytest.approx(2.5)
    assert result["robotics"] == pytest.approx(0.75)


def test_non_relevant_documents_reduce_term_weights():
    rocchio = Rocchio()
    result = rocchio.update_query(
        {"ai": 1.0},
        [],
        [{"ai": 2.0}],
    )

    assert result["ai"] == pytest.approx(0.7)


def test_negative_weights_are_removed():
    result = Rocchio().update_query(
        {"ai": 0.1},
        [],
        [{"ai": 2.0}],
    )

    assert "ai" not in result


def test_empty_feedback_preserves_query():
    query = {"ai": 1.0, "search": 0.5}

    assert Rocchio().update_query(query, []) == query


def test_negative_parameters_are_rejected():
    with pytest.raises(ValueError):
        Rocchio(alpha=-1)
