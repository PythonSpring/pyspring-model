import pytest
from unittest.mock import MagicMock
from py_spring_model.core.propagation_handlers.not_supported_handler import NotSupportedHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestNotSupportedHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_runs_without_transaction_when_none_exists(self):
        handler = NotSupportedHandler()
        result = handler.handle(lambda: "no txn")
        assert result == "no txn"

    def test_suspends_existing_transaction(self):
        outer_session = MagicMock()
        outer_state = TransactionState(session=outer_session, depth=1)
        SessionContextHolder.push_state(outer_state)

        captured = []
        handler = NotSupportedHandler()

        def capture():
            state = SessionContextHolder.current_state()
            captured.append(state)
            return "suspended"

        result = handler.handle(capture)

        assert result == "suspended"
        assert captured[0].session is None
        assert captured[0].depth == 0
        assert SessionContextHolder.current_state() is outer_state

    def test_restores_after_error(self):
        outer_session = MagicMock()
        outer_state = TransactionState(session=outer_session, depth=1)
        SessionContextHolder.push_state(outer_state)

        handler = NotSupportedHandler()

        def failing():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            handler.handle(failing)

        assert SessionContextHolder.current_state() is outer_state

    def test_passes_args_and_kwargs(self):
        handler = NotSupportedHandler()
        result = handler.handle(lambda a, b=2: a ** b, 3, b=3)
        assert result == 27
