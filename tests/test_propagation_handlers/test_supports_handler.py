import pytest
from unittest.mock import MagicMock
from py_spring_model.core.propagation_handlers.supports_handler import SupportsHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestSupportsHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_runs_without_transaction_when_none_exists(self):
        handler = SupportsHandler()
        result = handler.handle(lambda: "no txn")
        assert result == "no txn"
        assert SessionContextHolder.current_state() is None

    def test_joins_existing_transaction(self):
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = SupportsHandler()

        captured = []
        def capture():
            captured.append(SessionContextHolder.current_state())
            return "joined"

        result = handler.handle(capture)
        assert result == "joined"
        assert captured[0] is state
        existing_session.commit.assert_not_called()
        existing_session.rollback.assert_not_called()

    def test_passes_args_and_kwargs(self):
        handler = SupportsHandler()
        result = handler.handle(lambda x, y=1: x + y, 5, y=10)
        assert result == 15

    def test_exception_propagates_without_transaction(self):
        handler = SupportsHandler()

        def failing():
            raise ValueError("err")

        with pytest.raises(ValueError, match="err"):
            handler.handle(failing)
