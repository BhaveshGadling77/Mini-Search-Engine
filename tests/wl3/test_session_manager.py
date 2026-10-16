from wl3.feedback.session_manager import SessionManager


def test_create_session_returns_unique_ids():
    manager = SessionManager()

    first = manager.create_session()
    second = manager.create_session()

    assert first != second
    assert len(manager) == 2


def test_feedback_is_isolated_between_sessions():
    manager = SessionManager()
    session_a = manager.create_session()
    session_b = manager.create_session()

    manager.set_term_boosts(session_a, {"python": 1.5})
    manager.add_relevant_document(session_a, 42)

    assert manager.get_term_boosts(session_a) == {"python": 1.5}
    assert manager.get_term_boosts(session_b) == {}
    assert manager.get_or_create(session_b).relevant_doc_ids == set()


def test_feedback_snapshot_cannot_mutate_stored_state():
    manager = SessionManager()
    session_id = manager.create_session()

    state = manager.get_or_create(session_id)
    state.term_boosts["python"] = 10.0

    assert manager.get_term_boosts(session_id) == {}


def test_clear_feedback_keeps_session():
    manager = SessionManager()
    session_id = manager.create_session()

    manager.set_term_boosts(session_id, {"python": 1.0})
    manager.add_relevant_document(session_id, 5)
    manager.clear_feedback(session_id)

    assert not manager.has_feedback(session_id)
    assert manager.get_or_create(session_id).relevant_doc_ids == set()
    assert len(manager) == 1


def test_end_session_removes_session():
    manager = SessionManager()
    session_id = manager.create_session()

    assert manager.end_session(session_id) is True
    assert manager.end_session(session_id) is False
    assert len(manager) == 0


def test_empty_session_id_is_rejected():
    import pytest

    manager = SessionManager()

    with pytest.raises(ValueError):
        manager.get_or_create(" ")
