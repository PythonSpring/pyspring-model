import pytest
from unittest.mock import MagicMock, patch
from py_spring_model.core.propagation_handlers.required_handler import RequiredHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestRequiredHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_creates_new_transaction_when_none_exists(self):
        mock_session = MagicMock()
        handler = RequiredHandler()

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(lambda: "ok")

        assert result == "ok"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        assert SessionContextHolder.current_state() is None

    def test_joins_existing_transaction(self):
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = RequiredHandler()
        result = handler.handle(lambda: "joined")

        assert result == "joined"
        existing_session.commit.assert_not_called()
        existing_session.rollback.assert_not_called()
        assert state.depth == 1

    def test_rollback_on_error_new_transaction(self):
        mock_session = MagicMock()
        handler = RequiredHandler()

        def failing():
            raise ValueError("boom")

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(ValueError, match="boom"):
                handler.handle(failing)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_no_rollback_on_error_joined_transaction(self):
        """When joining, errors propagate but no commit/rollback - outer manages it."""
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        handler = RequiredHandler()

        def failing():
            raise ValueError("inner fail")

        with pytest.raises(ValueError):
            handler.handle(failing)

        existing_session.commit.assert_not_called()
        existing_session.rollback.assert_not_called()
        assert state.depth == 1

    def test_depth_tracking_during_join(self):
        existing_session = MagicMock()
        state = TransactionState(session=existing_session, depth=1)
        SessionContextHolder.push_state(state)

        captured_depths = []
        handler = RequiredHandler()

        def capture():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return "captured"

        handler.handle(capture)
        assert captured_depths == [2]
        assert state.depth == 1

    def test_passes_args_and_kwargs(self):
        mock_session = MagicMock()
        handler = RequiredHandler()

        def add(a, b, extra=0):
            return a + b + extra

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(add, 3, 4, extra=10)

        assert result == 17
