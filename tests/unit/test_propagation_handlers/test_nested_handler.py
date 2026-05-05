import pytest
from unittest.mock import MagicMock, patch
from py_spring_model.core.propagation_handlers.nested_handler import NestedHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestNestedHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_creates_new_transaction_when_none_exists(self):
        mock_session = MagicMock()
        handler = NestedHandler()

        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(lambda: "new txn")

        assert result == "new txn"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        assert SessionContextHolder.current_state() is None

    def test_creates_savepoint_within_existing_transaction(self):
        existing_session = MagicMock()
        nested_txn = MagicMock()
        existing_session.begin_nested.return_value = nested_txn
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = NestedHandler()
        result = handler.handle(lambda: "nested")

        assert result == "nested"
        existing_session.begin_nested.assert_called_once()
        nested_txn.commit.assert_called_once()
        existing_session.commit.assert_not_called()
        assert state.depth == 1

    def test_savepoint_rollback_on_error(self):
        existing_session = MagicMock()
        nested_txn = MagicMock()
        existing_session.begin_nested.return_value = nested_txn
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = NestedHandler()

        def failing():
            raise ValueError("inner error")

        with pytest.raises(ValueError, match="inner error"):
            handler.handle(failing)

        nested_txn.rollback.assert_called_once()
        nested_txn.commit.assert_not_called()
        existing_session.rollback.assert_not_called()
        assert SessionContextHolder.current_state() is state

    def test_rollback_on_error_new_transaction(self):
        mock_session = MagicMock()
        handler = NestedHandler()

        def failing():
            raise RuntimeError("fail")

        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(RuntimeError):
                handler.handle(failing)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_passes_args_and_kwargs(self):
        existing_session = MagicMock()
        nested_txn = MagicMock()
        existing_session.begin_nested.return_value = nested_txn
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = NestedHandler()
        result = handler.handle(lambda a, b: a + b, 10, 20)
        assert result == 30
