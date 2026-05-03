import pytest
from unittest.mock import MagicMock, patch
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestTransactionState:
    def test_transaction_state_defaults(self):
        state = TransactionState()
        assert state.session is None
        assert state.depth == 0

    def test_transaction_state_with_values(self):
        mock_session = MagicMock()
        state = TransactionState(session=mock_session, depth=2)
        assert state.session is mock_session
        assert state.depth == 2


class TestSessionContextHolderStack:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_stack_empty_initially(self):
        assert SessionContextHolder.current_state() is None
        assert not SessionContextHolder.has_active_transaction()

    def test_push_and_pop_state(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)
        assert SessionContextHolder.current_state() is state

        popped = SessionContextHolder.pop_state()
        assert popped is state
        assert SessionContextHolder.current_state() is None

    def test_stack_ordering(self):
        state1 = TransactionState(session=MagicMock(), depth=1)
        state2 = TransactionState(session=MagicMock(), depth=1)

        SessionContextHolder.push_state(state1)
        SessionContextHolder.push_state(state2)

        assert SessionContextHolder.current_state() is state2
        SessionContextHolder.pop_state()
        assert SessionContextHolder.current_state() is state1
        SessionContextHolder.pop_state()
        assert SessionContextHolder.current_state() is None

    def test_has_active_transaction_true(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)
        assert SessionContextHolder.has_active_transaction()

    def test_has_active_transaction_false_empty_stack(self):
        assert not SessionContextHolder.has_active_transaction()

    def test_has_active_transaction_false_no_session(self):
        state = TransactionState(session=None, depth=0)
        SessionContextHolder.push_state(state)
        assert not SessionContextHolder.has_active_transaction()

    def test_has_active_transaction_false_zero_depth(self):
        state = TransactionState(session=MagicMock(), depth=0)
        SessionContextHolder.push_state(state)
        assert not SessionContextHolder.has_active_transaction()

    def test_get_or_create_session_creates_when_no_state(self):
        mock_session = MagicMock()
        with patch("py_spring_model.core.session_context_holder.PySpringModel.create_session", return_value=mock_session):
            session = SessionContextHolder.get_or_create_session()
        assert session is mock_session

    def test_get_or_create_session_returns_existing(self):
        mock_session = MagicMock()
        state = TransactionState(session=mock_session, depth=1)
        SessionContextHolder.push_state(state)
        session = SessionContextHolder.get_or_create_session()
        assert session is mock_session

    def test_get_or_create_session_creates_when_state_has_no_session(self):
        state = TransactionState(session=None, depth=0)
        SessionContextHolder.push_state(state)
        mock_session = MagicMock()
        with patch("py_spring_model.core.session_context_holder.PySpringModel.create_session", return_value=mock_session):
            session = SessionContextHolder.get_or_create_session()
        assert session is mock_session
        assert SessionContextHolder.current_state().session is mock_session

    def test_clear_closes_all_sessions(self):
        session1 = MagicMock()
        session2 = MagicMock()
        SessionContextHolder.push_state(TransactionState(session=session1, depth=1))
        SessionContextHolder.push_state(TransactionState(session=session2, depth=1))

        SessionContextHolder.clear()

        session1.close.assert_called_once()
        session2.close.assert_called_once()
        assert SessionContextHolder.current_state() is None

    def test_clear_handles_none_sessions(self):
        SessionContextHolder.push_state(TransactionState(session=None, depth=0))
        SessionContextHolder.clear()  # should not raise
        assert SessionContextHolder.current_state() is None

    def test_pop_state_raises_on_empty_stack(self):
        with pytest.raises(IndexError):
            SessionContextHolder.pop_state()

    def test_clear_session_alias_works(self):
        session = MagicMock()
        SessionContextHolder.push_state(TransactionState(session=session, depth=1))
        SessionContextHolder.clear()
        assert SessionContextHolder.current_state() is None
        session.close.assert_called_once()

    def test_has_session_true(self):
        SessionContextHolder.push_state(TransactionState(session=MagicMock(), depth=1))
        assert SessionContextHolder.has_session()

    def test_has_session_false(self):
        assert not SessionContextHolder.has_session()
