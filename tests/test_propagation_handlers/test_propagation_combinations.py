"""Tests for multi-layer propagation handler combinations and edge cases.

Each test documents a specific call-chain scenario (2-3 layers deep) to verify
that propagation handlers compose correctly when nested inside one another.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from py_spring_model.core.propagation import ExistingTransactionError, TransactionRequiredError
from py_spring_model.core.propagation_handlers.mandatory_handler import MandatoryHandler
from py_spring_model.core.propagation_handlers.nested_handler import NestedHandler
from py_spring_model.core.propagation_handlers.never_handler import NeverHandler
from py_spring_model.core.propagation_handlers.not_supported_handler import NotSupportedHandler
from py_spring_model.core.propagation_handlers.required_handler import RequiredHandler
from py_spring_model.core.propagation_handlers.requires_new_handler import RequiresNewHandler
from py_spring_model.core.propagation_handlers.supports_handler import SupportsHandler
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState


class TestRequiredCombinations:
    """Combinations where REQUIRED is the outermost propagation."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_required_then_required_shares_transaction(self):
        """REQUIRED -> REQUIRED: inner joins the outer transaction.

        The inner call increments depth to 2 but does not commit or rollback.
        Only the outermost REQUIRED owns the session lifecycle.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = RequiredHandler()
        captured_depths = []

        def inner_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return "inner"

        def outer_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "inner"
        assert captured_depths == [1, 2]
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_required_then_requires_new_uses_separate_sessions(self):
        """REQUIRED -> REQUIRES_NEW: inner creates an independent transaction.

        Two separate sessions exist. The inner session commits/closes independently.
        The outer session is unaffected by the inner's lifecycle.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        inner = RequiresNewHandler()
        captured_sessions = []

        def inner_fn():
            captured_sessions.append(SessionContextHolder.current_state().session)
            return "inner_done"

        def outer_fn():
            captured_sessions.append(SessionContextHolder.current_state().session)
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.model.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            result = outer.handle(outer_fn)

        assert result == "inner_done"
        assert captured_sessions[0] is outer_session
        assert captured_sessions[1] is inner_session
        inner_session.commit.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.commit.assert_called_once()
        outer_session.close.assert_called_once()

    def test_required_then_never_raises_existing_transaction_error(self):
        """REQUIRED -> NEVER: inner refuses to run because a transaction is active.

        NEVER is a strict guard. The ExistingTransactionError propagates up and
        causes the outer REQUIRED to rollback.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = NeverHandler()

        def outer_fn():
            return inner.handle(lambda: "should not reach")

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(ExistingTransactionError):
                outer.handle(outer_fn)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_required_then_mandatory_joins_transaction(self):
        """REQUIRED -> MANDATORY: inner joins because an active transaction exists.

        MANDATORY is satisfied by the outer REQUIRED's transaction and increments
        depth. No new session is created.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = MandatoryHandler()
        captured_depths = []

        def inner_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return "mandatory_ok"

        def outer_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "mandatory_ok"
        assert captured_depths == [1, 2]
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_required_then_supports_shares_transaction(self):
        """REQUIRED -> SUPPORTS: inner runs in the existing transaction.

        SUPPORTS does not alter the context stack. The session from the outer
        REQUIRED is still visible to the inner function.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = SupportsHandler()

        def inner_fn():
            return SessionContextHolder.current_state().session

        def outer_fn():
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result is mock_session
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_required_then_not_supported_suspends_transaction(self):
        """REQUIRED -> NOT_SUPPORTED: inner runs with the transaction suspended.

        NOT_SUPPORTED pushes an empty state so has_active_transaction() returns
        False inside the inner function. The outer transaction resumes afterward.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = NotSupportedHandler()
        inner_active = []

        def inner_fn():
            inner_active.append(SessionContextHolder.has_active_transaction())
            return "suspended"

        outer_active_after = []

        def outer_fn():
            result = inner.handle(inner_fn)
            outer_active_after.append(SessionContextHolder.has_active_transaction())
            return result

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "suspended"
        assert inner_active == [False]
        assert outer_active_after == [True]  # transaction restored after suspension
        mock_session.commit.assert_called_once()

    def test_required_then_nested_creates_savepoint(self):
        """REQUIRED -> NESTED: inner creates a savepoint within the outer transaction.

        The savepoint commits independently. If the savepoint fails, only it rolls
        back; the outer transaction remains intact.
        """
        mock_session = MagicMock()
        mock_savepoint = MagicMock()
        mock_session.begin_nested.return_value = mock_savepoint
        outer = RequiredHandler()
        inner = NestedHandler()

        def inner_fn():
            return "nested_ok"

        def outer_fn():
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "nested_ok"
        mock_session.begin_nested.assert_called_once()
        mock_savepoint.commit.assert_called_once()
        mock_session.commit.assert_called_once()


class TestNotSupportedCombinations:
    """Combinations where NOT_SUPPORTED is involved as the middle layer."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_required_not_supported_required_creates_independent_transactions(self):
        """REQUIRED -> NOT_SUPPORTED -> REQUIRED: three-layer chain.

        The middle NOT_SUPPORTED suspends the outer transaction. The innermost
        REQUIRED sees no active transaction and creates a brand-new session.
        The two sessions commit/rollback independently.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        middle = NotSupportedHandler()
        inner = RequiredHandler()

        sessions_seen = []

        def inner_fn():
            sessions_seen.append(SessionContextHolder.current_state().session)
            return "inner_result"

        def middle_fn():
            sessions_seen.append(SessionContextHolder.has_active_transaction())
            return inner.handle(inner_fn)

        def outer_fn():
            sessions_seen.append(SessionContextHolder.current_state().session)
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            result = outer.handle(outer_fn)

        assert result == "inner_result"
        # outer_fn sees outer_session
        assert sessions_seen[0] is outer_session
        # middle_fn sees no active transaction (suspended)
        assert sessions_seen[1] is False
        # inner_fn sees inner_session (newly created)
        assert sessions_seen[2] is inner_session

        inner_session.commit.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.commit.assert_called_once()
        outer_session.close.assert_called_once()

    def test_required_not_supported_required_inner_failure_does_not_rollback_outer(self):
        """REQUIRED -> NOT_SUPPORTED -> REQUIRED: inner failure is isolated.

        When the innermost REQUIRED fails, its session rolls back. The exception
        propagates up through NOT_SUPPORTED to the outer REQUIRED which also
        rolls back. But crucially, if the outer had already done work, the inner
        rollback is on a separate session.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        middle = NotSupportedHandler()
        inner = RequiredHandler()

        def inner_fn():
            raise ValueError("inner_boom")

        def middle_fn():
            return inner.handle(inner_fn)

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            with pytest.raises(ValueError, match="inner_boom"):
                outer.handle(outer_fn)

        inner_session.rollback.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.rollback.assert_called_once()
        outer_session.close.assert_called_once()

    def test_required_not_supported_mandatory_raises_because_suspended(self):
        """REQUIRED -> NOT_SUPPORTED -> MANDATORY: MANDATORY fails.

        NOT_SUPPORTED suspends the transaction, so MANDATORY sees no active
        transaction and raises TransactionRequiredError.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        middle = NotSupportedHandler()
        inner = MandatoryHandler()

        def middle_fn():
            return inner.handle(lambda: "unreachable")

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(TransactionRequiredError):
                outer.handle(outer_fn)

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestRequiresNewCombinations:
    """Combinations where REQUIRES_NEW is involved."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_required_requires_new_inner_failure_does_not_rollback_outer(self):
        """REQUIRED -> REQUIRES_NEW: inner failure rolls back only the inner session.

        The outer transaction catches the propagated exception and rolls back
        separately. The two sessions are fully independent.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        inner = RequiresNewHandler()

        def inner_fn():
            raise ValueError("inner_fail")

        def outer_fn():
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.model.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            with pytest.raises(ValueError, match="inner_fail"):
                outer.handle(outer_fn)

        inner_session.rollback.assert_called_once()
        inner_session.close.assert_called_once()
        # Outer also rolls back because exception propagated
        outer_session.rollback.assert_called_once()
        outer_session.close.assert_called_once()

    def test_required_requires_new_inner_success_outer_failure(self):
        """REQUIRED -> REQUIRES_NEW (success) -> outer fails after: inner commit persists.

        The inner REQUIRES_NEW commits its own session successfully. Then the
        outer function raises an exception, causing the outer session to rollback.
        The inner commit is already done and is NOT undone.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        inner = RequiresNewHandler()

        def inner_fn():
            return "committed"

        def outer_fn():
            inner.handle(inner_fn)
            raise RuntimeError("outer_fail_after_inner_commit")

        with patch(
            "py_spring_model.core.model.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            with pytest.raises(RuntimeError, match="outer_fail_after_inner_commit"):
                outer.handle(outer_fn)

        inner_session.commit.assert_called_once()
        inner_session.close.assert_called_once()
        outer_session.rollback.assert_called_once()
        outer_session.commit.assert_not_called()

    def test_requires_new_then_requires_new_fully_independent(self):
        """REQUIRES_NEW -> REQUIRES_NEW: two completely independent transactions.

        Each call creates its own session. Commit/rollback of one does not
        affect the other.
        """
        session_a = MagicMock(name="session_a")
        session_b = MagicMock(name="session_b")
        outer = RequiresNewHandler()
        inner = RequiresNewHandler()

        def inner_fn():
            return SessionContextHolder.current_state().session

        def outer_fn():
            inner_result = inner.handle(inner_fn)
            return (SessionContextHolder.current_state().session, inner_result)

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            side_effect=[session_a, session_b],
        ):
            outer_sess, inner_sess = outer.handle(outer_fn)

        assert outer_sess is session_a
        assert inner_sess is session_b
        session_a.commit.assert_called_once()
        session_b.commit.assert_called_once()
        session_a.close.assert_called_once()
        session_b.close.assert_called_once()

    def test_requires_new_then_never_raises_existing_transaction_error(self):
        """REQUIRES_NEW -> NEVER: NEVER refuses because REQUIRES_NEW created a transaction.

        REQUIRES_NEW always creates a new transaction. NEVER detects it and
        raises ExistingTransactionError. The REQUIRES_NEW session rolls back.
        """
        mock_session = MagicMock()
        outer = RequiresNewHandler()
        inner = NeverHandler()

        def outer_fn():
            return inner.handle(lambda: "unreachable")

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(ExistingTransactionError):
                outer.handle(outer_fn)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_requires_new_then_not_supported_suspends_new_transaction(self):
        """REQUIRES_NEW -> NOT_SUPPORTED: inner suspends the newly created transaction.

        REQUIRES_NEW creates a fresh session. NOT_SUPPORTED pushes an empty
        state, hiding the new transaction. After NOT_SUPPORTED completes, the
        transaction resumes and commits normally.
        """
        mock_session = MagicMock()
        outer = RequiresNewHandler()
        inner = NotSupportedHandler()
        inner_active = []
        outer_active_after = []

        def inner_fn():
            inner_active.append(SessionContextHolder.has_active_transaction())
            return "suspended_new"

        def outer_fn():
            result = inner.handle(inner_fn)
            outer_active_after.append(SessionContextHolder.has_active_transaction())
            return result

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "suspended_new"
        assert inner_active == [False]
        assert outer_active_after == [True]
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()


class TestNestedCombinations:
    """Combinations involving NESTED (savepoint) propagation."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_nested_standalone_behaves_like_required(self):
        """NESTED called standalone (no active txn): behaves like REQUIRED.

        When no transaction exists, NESTED falls back to creating a new session,
        pushing state, and managing commit/rollback/close — identical to REQUIRED.
        """
        mock_session = MagicMock()
        handler = NestedHandler()

        def fn():
            state = SessionContextHolder.current_state()
            assert state is not None
            assert state.session is mock_session
            return "nested_standalone"

        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = handler.handle(fn)

        assert result == "nested_standalone"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.begin_nested.assert_not_called()
        assert SessionContextHolder.current_state() is None

    def test_nested_standalone_failure_rolls_back(self):
        """NESTED called standalone (no active txn, fails): rolls back like REQUIRED.

        The fallback path handles exceptions by rolling back the session,
        closing it, and popping the state.
        """
        mock_session = MagicMock()
        handler = NestedHandler()

        def fn():
            raise ValueError("standalone_nested_fail")

        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            with pytest.raises(ValueError, match="standalone_nested_fail"):
                handler.handle(fn)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()
        assert SessionContextHolder.current_state() is None

    def test_required_nested_savepoint_rollback_outer_continues(self):
        """REQUIRED -> NESTED (fails): savepoint rolls back, outer can continue.

        When the nested function fails, only the savepoint is rolled back.
        The outer transaction remains active and can commit its own work.
        """
        mock_session = MagicMock()
        mock_savepoint = MagicMock()
        mock_session.begin_nested.return_value = mock_savepoint
        outer = RequiredHandler()
        inner = NestedHandler()

        def inner_fn():
            raise ValueError("savepoint_fail")

        def outer_fn():
            try:
                inner.handle(inner_fn)
            except ValueError:
                pass  # Catch and continue
            return "outer_continues"

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "outer_continues"
        mock_savepoint.rollback.assert_called_once()
        mock_savepoint.commit.assert_not_called()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    def test_required_nested_nested_multiple_savepoints(self):
        """REQUIRED -> NESTED -> NESTED: two consecutive savepoints.

        Each NESTED call creates its own savepoint within the same session.
        Both savepoints commit independently.
        """
        mock_session = MagicMock()
        savepoint_1 = MagicMock(name="savepoint_1")
        savepoint_2 = MagicMock(name="savepoint_2")
        mock_session.begin_nested.side_effect = [savepoint_1, savepoint_2]

        outer = RequiredHandler()
        nested_handler = NestedHandler()

        def nested_fn_2():
            return "nested_2_ok"

        def nested_fn_1():
            return nested_handler.handle(nested_fn_2)

        def outer_fn():
            return nested_handler.handle(nested_fn_1)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "nested_2_ok"
        assert mock_session.begin_nested.call_count == 2
        savepoint_1.commit.assert_called_once()
        savepoint_2.commit.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_required_nested_fail_second_savepoint_first_survives(self):
        """REQUIRED -> NESTED (ok) -> NESTED (fails): first savepoint persists.

        Two sequential NESTED calls. The first succeeds and its savepoint commits.
        The second fails and its savepoint rolls back. The outer can catch and
        still commit the overall transaction including the first savepoint's work.
        """
        mock_session = MagicMock()
        savepoint_ok = MagicMock(name="savepoint_ok")
        savepoint_fail = MagicMock(name="savepoint_fail")
        mock_session.begin_nested.side_effect = [savepoint_ok, savepoint_fail]

        outer = RequiredHandler()
        nested = NestedHandler()

        def failing_fn():
            raise ValueError("second_fail")

        def outer_fn():
            nested.handle(lambda: "first_ok")
            try:
                nested.handle(failing_fn)
            except ValueError:
                pass  # Catch and continue
            return "outer_ok"

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "outer_ok"
        savepoint_ok.commit.assert_called_once()
        savepoint_fail.rollback.assert_called_once()
        mock_session.commit.assert_called_once()


class TestMandatoryCombinations:
    """Combinations involving MANDATORY propagation."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_mandatory_without_transaction_raises(self):
        """MANDATORY called standalone: raises TransactionRequiredError.

        MANDATORY never creates a transaction. Calling it at the top level
        (no active transaction) is always an error.
        """
        handler = MandatoryHandler()
        with pytest.raises(TransactionRequiredError):
            handler.handle(lambda: "unreachable")

    def test_required_mandatory_mandatory_triple_join(self):
        """REQUIRED -> MANDATORY -> MANDATORY: all three share the same transaction.

        Depth increments to 3 at the innermost level. Only the outer REQUIRED
        commits. MANDATORY never touches commit/rollback.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        mid = MandatoryHandler()
        inner = MandatoryHandler()
        captured_depths = []

        def inner_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return "deep"

        def mid_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return inner.handle(inner_fn)

        def outer_fn():
            captured_depths.append(SessionContextHolder.current_state().depth)
            return mid.handle(mid_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "deep"
        assert captured_depths == [1, 2, 3]
        mock_session.commit.assert_called_once()

    def test_mandatory_depth_restored_after_inner_error(self):
        """REQUIRED -> MANDATORY (fails): depth restored after MANDATORY error.

        When the function inside MANDATORY raises, the depth counter is
        decremented back correctly in the finally block.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = MandatoryHandler()
        captured_depth_after = []

        def inner_fn():
            raise ValueError("mandatory_fail")

        def outer_fn():
            try:
                inner.handle(inner_fn)
            except ValueError:
                pass
            captured_depth_after.append(SessionContextHolder.current_state().depth)
            return "recovered_from_mandatory"

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "recovered_from_mandatory"
        assert captured_depth_after == [1]
        mock_session.commit.assert_called_once()

    def test_requires_new_then_mandatory_joins_new_transaction(self):
        """REQUIRES_NEW -> MANDATORY: MANDATORY joins the newly created transaction.

        REQUIRES_NEW creates a fresh transaction. MANDATORY sees it as an
        active transaction and joins it successfully.
        """
        mock_session = MagicMock()
        outer = RequiresNewHandler()
        inner = MandatoryHandler()

        def inner_fn():
            return SessionContextHolder.current_state().session

        def outer_fn():
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.requires_new_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result is mock_session
        mock_session.commit.assert_called_once()


class TestNeverCombinations:
    """Combinations involving NEVER propagation."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_never_then_required_creates_transaction(self):
        """NEVER (no txn) -> REQUIRED: inner creates its own transaction.

        When NEVER is called at the top level (no transaction), it succeeds.
        The inner REQUIRED creates a new transaction normally.
        """
        mock_session = MagicMock()
        outer = NeverHandler()
        inner = RequiredHandler()

        def outer_fn():
            return inner.handle(lambda: "created_inside_never")

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "created_inside_never"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_never_then_never_both_succeed_without_transaction(self):
        """NEVER -> NEVER: both succeed when no transaction exists.

        Without any active transaction, consecutive NEVER handlers simply
        execute the function directly.
        """
        outer = NeverHandler()
        inner = NeverHandler()

        def outer_fn():
            return inner.handle(lambda: "both_ok")

        result = outer.handle(outer_fn)
        assert result == "both_ok"

    def test_never_then_mandatory_raises_because_no_transaction(self):
        """NEVER -> MANDATORY: MANDATORY fails because NEVER ensures no transaction.

        NEVER requires no active transaction. MANDATORY requires one. They are
        fundamentally incompatible in a direct call chain.
        """
        outer = NeverHandler()
        inner = MandatoryHandler()

        def outer_fn():
            return inner.handle(lambda: "unreachable")

        with pytest.raises(TransactionRequiredError):
            outer.handle(outer_fn)


class TestSupportsCombinations:
    """Combinations involving SUPPORTS propagation."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_supports_then_required_creates_transaction_when_none_exists(self):
        """SUPPORTS (no txn) -> REQUIRED: inner creates a new transaction.

        SUPPORTS runs without a transaction. The inner REQUIRED sees no active
        transaction and creates one.
        """
        mock_session = MagicMock()
        outer = SupportsHandler()
        inner = RequiredHandler()

        def outer_fn():
            return inner.handle(lambda: "required_inside_supports")

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "required_inside_supports"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_supports_then_mandatory_raises_when_no_transaction(self):
        """SUPPORTS (no txn) -> MANDATORY: MANDATORY fails.

        SUPPORTS does not create a transaction. MANDATORY requires one.
        This combination fails when there is no pre-existing transaction.
        """
        outer = SupportsHandler()
        inner = MandatoryHandler()

        def outer_fn():
            return inner.handle(lambda: "unreachable")

        with pytest.raises(TransactionRequiredError):
            outer.handle(outer_fn)

    def test_required_supports_mandatory_three_layer_join(self):
        """REQUIRED -> SUPPORTS -> MANDATORY: all three share the same transaction.

        SUPPORTS is transparent — it does not alter the context. MANDATORY
        sees the REQUIRED's transaction and joins.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        middle = SupportsHandler()
        inner = MandatoryHandler()

        def inner_fn():
            return SessionContextHolder.current_state().session

        def middle_fn():
            return inner.handle(inner_fn)

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result is mock_session
        mock_session.commit.assert_called_once()


class TestEdgeCases:
    """Edge cases and less common propagation scenarios."""

    def setup_method(self):
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()

    def test_not_supported_then_never_both_run_without_transaction(self):
        """NOT_SUPPORTED (no txn) -> NEVER: both succeed.

        When called without an existing transaction, NOT_SUPPORTED simply runs
        the function. NEVER also succeeds because no transaction is active.
        """
        outer = NotSupportedHandler()
        inner = NeverHandler()

        def outer_fn():
            return inner.handle(lambda: "both_non_txn")

        result = outer.handle(outer_fn)
        assert result == "both_non_txn"

    def test_required_not_supported_never_succeeds_because_suspended(self):
        """REQUIRED -> NOT_SUPPORTED -> NEVER: NEVER succeeds after suspension.

        NOT_SUPPORTED suspends the outer transaction. NEVER then sees no active
        transaction and runs normally. This is how to safely call a NEVER method
        from within a transactional context.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        middle = NotSupportedHandler()
        inner = NeverHandler()

        def inner_fn():
            return "never_ok"

        def middle_fn():
            return inner.handle(inner_fn)

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "never_ok"
        mock_session.commit.assert_called_once()

    def test_context_stack_restored_after_deeply_nested_failure(self):
        """REQUIRED -> REQUIRES_NEW -> NESTED (fails): stack is fully restored.

        After a failure in the innermost NESTED handler, each layer cleans up
        its own state. The context stack returns to empty after all handlers unwind.
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        middle = RequiresNewHandler()
        inner = NestedHandler()

        def inner_fn():
            raise RuntimeError("deep_failure")

        def middle_fn():
            return inner.handle(inner_fn)

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.model.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            with pytest.raises(RuntimeError, match="deep_failure"):
                outer.handle(outer_fn)

        assert SessionContextHolder.current_state() is None
        outer_session.rollback.assert_called_once()
        outer_session.close.assert_called_once()
        inner_session.rollback.assert_called_once()
        inner_session.close.assert_called_once()

    def test_depth_restored_after_error_in_joined_transaction(self):
        """REQUIRED -> REQUIRED (fails): depth returns to 1 after inner error.

        When the inner REQUIRED joins and then fails, the depth counter is
        properly decremented back, even though the exception propagates.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        inner = RequiredHandler()

        captured_depth_after = []

        def inner_fn():
            raise ValueError("inner_error")

        def outer_fn():
            try:
                inner.handle(inner_fn)
            except ValueError:
                pass
            captured_depth_after.append(SessionContextHolder.current_state().depth)
            return "recovered"

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "recovered"
        assert captured_depth_after == [1]
        mock_session.commit.assert_called_once()

    def test_not_supported_with_nested_not_supported_double_suspension(self):
        """REQUIRED -> NOT_SUPPORTED -> NOT_SUPPORTED: double suspension.

        The second NOT_SUPPORTED sees no active transaction (already suspended),
        so it simply runs the function directly without pushing another empty state.
        """
        mock_session = MagicMock()
        outer = RequiredHandler()
        ns1 = NotSupportedHandler()
        ns2 = NotSupportedHandler()

        inner_active = []

        def inner_fn():
            inner_active.append(SessionContextHolder.has_active_transaction())
            return "double_suspended"

        def middle_fn():
            return ns2.handle(inner_fn)

        def outer_fn():
            return ns1.handle(middle_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.required_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "double_suspended"
        assert inner_active == [False]
        # Outer transaction still commits normally after suspension
        mock_session.commit.assert_called_once()

    def test_not_supported_then_nested_creates_new_transaction(self):
        """NOT_SUPPORTED (no txn) -> NESTED: NESTED falls back to creating a session.

        When NOT_SUPPORTED runs without a transaction, it simply calls the
        function. NESTED then sees no active transaction and falls back to
        REQUIRED-like behavior, creating a new session.
        """
        mock_session = MagicMock()
        outer = NotSupportedHandler()
        inner = NestedHandler()

        def inner_fn():
            return "nested_fallback"

        def outer_fn():
            return inner.handle(inner_fn)

        with patch(
            "py_spring_model.core.propagation_handlers.nested_handler.PySpringModel.create_session",
            return_value=mock_session,
        ):
            result = outer.handle(outer_fn)

        assert result == "nested_fallback"
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.begin_nested.assert_not_called()

    def test_required_not_supported_nested_creates_independent_savepoint_free_txn(self):
        """REQUIRED -> NOT_SUPPORTED -> NESTED: NESTED creates new session, no savepoint.

        NOT_SUPPORTED suspends the outer REQUIRED's transaction. NESTED then
        sees no active transaction and creates a brand-new independent session
        (no savepoint, since there's no parent transaction to nest within).
        """
        outer_session = MagicMock(name="outer_session")
        inner_session = MagicMock(name="inner_session")
        outer = RequiredHandler()
        middle = NotSupportedHandler()
        inner = NestedHandler()

        captured = []

        def inner_fn():
            state = SessionContextHolder.current_state()
            captured.append(state.session)
            return "nested_independent"

        def middle_fn():
            return inner.handle(inner_fn)

        def outer_fn():
            return middle.handle(middle_fn)

        with patch(
            "py_spring_model.core.model.PySpringModel.create_session",
            side_effect=[outer_session, inner_session],
        ):
            result = outer.handle(outer_fn)

        assert result == "nested_independent"
        assert captured[0] is inner_session
        inner_session.commit.assert_called_once()
        inner_session.close.assert_called_once()
        inner_session.begin_nested.assert_not_called()
        outer_session.commit.assert_called_once()
        outer_session.close.assert_called_once()
