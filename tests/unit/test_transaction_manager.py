import pytest
from unittest.mock import MagicMock, patch
from py_spring_model.core.transaction_manager import TransactionManager
from py_spring_model.core.propagation import Propagation, TransactionRequiredError, ExistingTransactionError
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestTransactionManager:
    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_dispatches_to_required_handler(self):
        mock_session = MagicMock()
        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = TransactionManager.execute(lambda: "req", Propagation.REQUIRED)
        assert result == "req"
        mock_session.commit.assert_called_once()

    def test_dispatches_to_requires_new_handler(self):
        mock_session = MagicMock()
        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = TransactionManager.execute(lambda: "new", Propagation.REQUIRES_NEW)
        assert result == "new"
        mock_session.commit.assert_called_once()

    def test_dispatches_to_supports_handler(self):
        result = TransactionManager.execute(lambda: "sup", Propagation.SUPPORTS)
        assert result == "sup"

    def test_dispatches_to_mandatory_handler_raises(self):
        with pytest.raises(TransactionRequiredError):
            TransactionManager.execute(lambda: None, Propagation.MANDATORY)

    def test_dispatches_to_not_supported_handler(self):
        result = TransactionManager.execute(lambda: "not_sup", Propagation.NOT_SUPPORTED)
        assert result == "not_sup"

    def test_dispatches_to_never_handler(self):
        result = TransactionManager.execute(lambda: "never", Propagation.NEVER)
        assert result == "never"

    def test_dispatches_to_never_handler_raises_with_txn(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)
        with pytest.raises(ExistingTransactionError):
            TransactionManager.execute(lambda: None, Propagation.NEVER)

    def test_dispatches_to_nested_handler(self):
        mock_session = MagicMock()
        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = TransactionManager.execute(lambda: "nested", Propagation.NESTED)
        assert result == "nested"
        mock_session.commit.assert_called_once()

    def test_all_propagation_modes_have_handlers(self):
        for prop in Propagation:
            assert prop in TransactionManager._handlers, f"Missing handler for {prop}"

    def test_passes_args_and_kwargs(self):
        mock_session = MagicMock()
        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = TransactionManager.execute(
                lambda a, b: a + b, Propagation.REQUIRED, 3, 4
            )
        assert result == 7
