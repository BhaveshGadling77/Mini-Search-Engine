"""Thread-safe, in-memory session management for Rocchio feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4


@dataclass
class SessionFeedbackState:
    """Personalized feedback state belonging to one session."""

    term_boosts: dict[str, float] = field(default_factory=dict)
    relevant_doc_ids: set[int] = field(default_factory=set)

    @property
    def has_feedback(self) -> bool:
        return bool(self.term_boosts)


class SessionManager:
    """Manage anonymous sessions and isolate their feedback state."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionFeedbackState] = {}
        self._lock = RLock()

    def create_session(self) -> str:
        """Create a new session and return its unique identifier."""
        with self._lock:
            session_id = str(uuid4())
            self._sessions[session_id] = SessionFeedbackState()
            return session_id

    def get_or_create(
        self, session_id: str
    ) -> SessionFeedbackState:
        """Return the state for a session, creating it if necessary."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must not be empty")

        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionFeedbackState()

            state = self._sessions[session_id]

            # Return a snapshot so callers cannot mutate shared state
            # without acquiring the manager's lock.
            return SessionFeedbackState(
                term_boosts=state.term_boosts.copy(),
                relevant_doc_ids=state.relevant_doc_ids.copy(),
            )

    def get_term_boosts(self, session_id: str) -> dict[str, float]:
        """Return a copy of the session's personalized term weights."""
        return self.get_or_create(session_id).term_boosts

    def set_term_boosts(
        self,
        session_id: str,
        boosts: dict[str, float],
    ) -> None:
        """Replace the session's personalized term weights."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must not be empty")

        clean_boosts = {
            term: float(weight)
            for term, weight in boosts.items()
            if weight > 0
        }

        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionFeedbackState()

            self._sessions[session_id].term_boosts = clean_boosts

    def add_relevant_document(
        self,
        session_id: str,
        doc_id: int,
    ) -> None:
        """Record a document marked relevant in this session."""
        if not session_id or not session_id.strip():
            raise ValueError("session_id must not be empty")

        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionFeedbackState()

            self._sessions[session_id].relevant_doc_ids.add(doc_id)

    def has_feedback(self, session_id: str) -> bool:
        """Whether this session currently has personalized term boosts."""
        return self.get_or_create(session_id).has_feedback

    def clear_feedback(self, session_id: str) -> None:
        """Clear feedback while keeping the session alive."""
        with self._lock:
            state = self._sessions.get(session_id)
            if state is not None:
                state.term_boosts.clear()
                state.relevant_doc_ids.clear()

    def end_session(self, session_id: str) -> bool:
        """Remove a session. Return whether it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def __len__(self) -> int:
        """Return the number of active sessions."""
        with self._lock:
            return len(self._sessions)
