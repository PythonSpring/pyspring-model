import pytest
from unittest.mock import MagicMock
from py_spring_model.core.propagation_handlers.never_handler import NeverHandler
from py_spring_model.core.propagation import ExistingTransactionError
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestNeverHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_runs_when_no_transaction_exists(self):
        handler = NeverHandler()
        result = handler.handle(lambda: "ok")
        assert result == "ok"

    def test_raises_when_transaction_exists(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)

        handler = NeverHandler()
        with pytest.raises(ExistingTransactionError):
            handler.handle(lambda: "should not run")

    def test_passes_args_and_kwargs(self):
        handler = NeverHandler()
        result = handler.handle(lambda x, y: f"{x}-{y}", "a", "b")
        assert result == "a-b"
