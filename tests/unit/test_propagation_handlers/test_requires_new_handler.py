import pytest
from unittest.mock import MagicMock, patch
from py_spring_model.core.propagation_handlers.requires_new_handler import RequiresNewHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestRequiresNewHandler:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_creates_new_session_when_none_exists(self):
        mock_session = MagicMock()
        handler = RequiresNewHandler()

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(lambda: "created")

        assert result == "created"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        assert SessionContextHolder.current_state() is None

    def test_creates_new_session_even_when_transaction_exists(self):
        outer_session = MagicMock()
        outer_state = TransactionState(session=outer_session, depth=1)
        SessionContextHolder.push_state(outer_state)

        inner_session = MagicMock()
        handler = RequiresNewHandler()

        captured_sessions = []

        def capture():
            state = SessionContextHolder.current_state()
            captured_sessions.append(state.session)
            return "new"

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=inner_session,
        ):
            result = handler.handle(capture)

        assert result == "new"
        assert captured_sessions[0] is inner_session
        inner_session.commit.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.commit.assert_not_called()
        outer_session.rollback.assert_not_called()
        assert SessionContextHolder.current_state() is outer_state

    def test_outer_session_untouched_after_inner_failure(self):
        outer_session = MagicMock()
        outer_state = TransactionState(session=outer_session, depth=1)
        SessionContextHolder.push_state(outer_state)

        inner_session = MagicMock()
        handler = RequiresNewHandler()

        def failing():
            raise ValueError("inner boom")

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=inner_session,
        ):
            with pytest.raises(ValueError, match="inner boom"):
                handler.handle(failing)

        inner_session.rollback.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.commit.assert_not_called()
        outer_session.rollback.assert_not_called()
        assert SessionContextHolder.current_state() is outer_state

    def test_rollback_on_error_no_existing_transaction(self):
        mock_session = MagicMock()
        handler = RequiresNewHandler()

        def failing():
            raise RuntimeError("fail")

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(RuntimeError):
                handler.handle(failing)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_passes_args_and_kwargs(self):
        mock_session = MagicMock()
        handler = RequiresNewHandler()

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(lambda a, b: a * b, 3, 7)

        assert result == 21
