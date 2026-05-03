import pytest
from unittest.mock import MagicMock
from py_spring_model.core.propagation_handlers.mandatory_handler import MandatoryHandler
from py_spring_model.core.propagation import TransactionRequiredError
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestMandatoryHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_raises_when_no_active_transaction(self):
        handler = MandatoryHandler()
        with pytest.raises(TransactionRequiredError):
            handler.handle(lambda: "should not run")

    def test_joins_existing_transaction(self):
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = MandatoryHandler()
        result = handler.handle(lambda: "mandatory joined")

        assert result == "mandatory joined"
        existing_session.commit.assert_not_called()
        existing_session.rollback.assert_not_called()
        assert state.depth == 1

    def test_depth_tracking_during_join(self):
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        captured_depths = []
        handler = MandatoryHandler()

        def capture():
            captured_depths.append(SessionContextHolder.current_state().depth)

        handler.handle(capture)
        assert captured_depths == [2]
        assert state.depth == 1

    def test_passes_args_and_kwargs(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)

        handler = MandatoryHandler()
        result = handler.handle(lambda a, b: a - b, 10, 3)
        assert result == 7
