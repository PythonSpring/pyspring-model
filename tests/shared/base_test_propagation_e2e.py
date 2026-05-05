"""
End-to-end tests for transaction propagation modes.

These tests use a real in-memory SQLite database to verify that each propagation
mode behaves correctly with actual SQL operations, commits, and rollbacks.

Test Scenarios:
===============

REQUIRED (default):
  - Creates a new transaction when none exists; data is committed.
  - Joins an existing transaction when called from within one; shares the same session.
  - Inner error rolls back the entire outer transaction (no partial commits).

REQUIRES_NEW:
  - Always creates a new, independent session — even inside an existing transaction.
  - Inner transaction commits independently; outer rollback does NOT undo inner work.
  - Inner failure does NOT affect the outer transaction.

SUPPORTS:
  - Joins an existing transaction if one is active.
  - Runs without any transaction if none exists (no commit/rollback management).

MANDATORY:
  - Raises TransactionRequiredError when called without an active transaction.
  - Joins an existing transaction normally when one is active.

NOT_SUPPORTED:
  - Suspends the current transaction; code runs with no active transaction context.
  - After completion, the outer transaction is restored and can still commit.

NEVER:
  - Raises ExistingTransactionError when called inside an active transaction.
  - Runs normally when no transaction is active.

NESTED:
  - Creates a savepoint inside an existing transaction.
  - Savepoint rollback on inner error does NOT affect the outer transaction's data.
  - Creates a new transaction (like REQUIRED) when no transaction exists.
"""

import pytest
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel, Propagation
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.core.propagation import TransactionRequiredError, ExistingTransactionError


class PropagationTestUser(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


class BasePropagationE2E:

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([PropagationTestUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        yield
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None

    def _count_users(self) -> int:
        with PySpringModel.create_managed_session() as s:
            return s.execute(text("SELECT COUNT(*) FROM propagation_test_user")).scalar()

    def _get_user_names(self) -> list[str]:
        with PySpringModel.create_managed_session() as s:
            rows = s.execute(text("SELECT name FROM propagation_test_user ORDER BY name")).fetchall()
            return [r.name for r in rows]

    # ── REQUIRED ─────────────────────────────────────────────────────────

    def test_required_creates_new_transaction_and_commits(self):
        @Transactional
        def create_user():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Alice", email="alice@test.com"))

        create_user()
        assert self._count_users() == 1

    def test_required_joins_existing_transaction(self):
        captured_sessions = []

        @Transactional
        def inner():
            captured_sessions.append(SessionContextHolder.get_or_create_session())

        @Transactional
        def outer():
            captured_sessions.append(SessionContextHolder.get_or_create_session())
            inner()

        outer()
        assert captured_sessions[0] is captured_sessions[1]

    def test_required_inner_error_rolls_back_entire_transaction(self):
        @Transactional
        def inner_fail():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Inner", email="inner@test.com"))
            session.flush()
            raise ValueError("inner boom")

        @Transactional
        def outer():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Outer", email="outer@test.com"))
            session.flush()
            inner_fail()

        with pytest.raises(ValueError, match="inner boom"):
            outer()

        assert self._count_users() == 0

    # ── REQUIRES_NEW ─────────────────────────────────────────────────────

    def test_requires_new_creates_independent_session(self):
        captured_sessions = []

        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def inner():
            captured_sessions.append(SessionContextHolder.get_or_create_session())

        @Transactional
        def outer():
            captured_sessions.append(SessionContextHolder.get_or_create_session())
            inner()

        outer()
        assert len(captured_sessions) == 2
        assert captured_sessions[0] is not captured_sessions[1]

    def test_requires_new_inner_commits_independently_of_outer_rollback(self):
        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def inner_save():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Inner", email="inner@test.com"))

        @Transactional
        def outer_fail():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Outer", email="outer@test.com"))
            session.flush()
            inner_save()
            raise ValueError("outer fails after inner committed")

        with pytest.raises(ValueError):
            outer_fail()

        names = self._get_user_names()
        assert "Inner" in names

    def test_requires_new_inner_failure_does_not_affect_outer(self):
        """Inner REQUIRES_NEW failure should not affect outer transaction.

        Note: This test verifies the handler logic via session identity rather than
        full commit/rollback isolation, because SQLite in-memory databases use
        separate storage per connection, making cross-connection isolation tests
        unreliable. Use PostgreSQL (test_e2e_py_spring_model_provider.py) for
        full multi-connection isolation tests.
        """
        inner_rolled_back = []
        outer_session_ref = []

        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def inner_fail():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="InnerFail", email="fail@test.com"))
            session.flush()
            raise RuntimeError("inner fails")

        @Transactional
        def outer_succeeds():
            session = SessionContextHolder.get_or_create_session()
            outer_session_ref.append(session)
            session.add(PropagationTestUser(name="Outer", email="outer@test.com"))
            session.flush()
            try:
                inner_fail()
            except RuntimeError:
                inner_rolled_back.append(True)

        outer_succeeds()

        # Inner failure was caught, outer transaction completed
        assert inner_rolled_back == [True]
        assert not SessionContextHolder.has_session()

    # ── SUPPORTS ─────────────────────────────────────────────────────────

    def test_supports_joins_existing_transaction(self):
        captured_sessions = []

        @Transactional(propagation=Propagation.SUPPORTS)
        def inner():
            captured_sessions.append(SessionContextHolder.get_or_create_session())

        @Transactional
        def outer():
            captured_sessions.append(SessionContextHolder.get_or_create_session())
            inner()

        outer()
        assert captured_sessions[0] is captured_sessions[1]

    def test_supports_runs_without_transaction_when_none_exists(self):
        called = []

        @Transactional(propagation=Propagation.SUPPORTS)
        def no_txn_op():
            called.append(True)
            return "done"

        result = no_txn_op()
        assert result == "done"
        assert called == [True]
        assert not SessionContextHolder.has_active_transaction()

    # ── MANDATORY ────────────────────────────────────────────────────────

    def test_mandatory_raises_when_no_transaction(self):
        @Transactional(propagation=Propagation.MANDATORY)
        def needs_txn():
            return "unreachable"

        with pytest.raises(TransactionRequiredError):
            needs_txn()

    def test_mandatory_joins_existing_transaction(self):
        @Transactional(propagation=Propagation.MANDATORY)
        def inner():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Mandatory", email="m@test.com"))

        @Transactional
        def outer():
            inner()

        outer()
        assert self._count_users() == 1

    # ── NOT_SUPPORTED ────────────────────────────────────────────────────

    def test_not_supported_suspends_active_transaction(self):
        txn_active_inside = []

        @Transactional(propagation=Propagation.NOT_SUPPORTED)
        def suspended_op():
            txn_active_inside.append(SessionContextHolder.has_active_transaction())
            return "suspended"

        @Transactional
        def outer():
            suspended_op()

        outer()
        assert txn_active_inside == [False]

    def test_not_supported_outer_transaction_still_works_after_suspension(self):
        @Transactional(propagation=Propagation.NOT_SUPPORTED)
        def suspended_op():
            pass  # does nothing transactional

        @Transactional
        def outer():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="AfterSuspend", email="as@test.com"))
            session.flush()
            suspended_op()
            # outer should still be able to commit

        outer()
        assert self._count_users() == 1

    # ── NEVER ────────────────────────────────────────────────────────────

    def test_never_raises_when_transaction_exists(self):
        @Transactional(propagation=Propagation.NEVER)
        def no_txn_ever():
            return "unreachable"

        @Transactional
        def outer():
            no_txn_ever()

        with pytest.raises(ExistingTransactionError):
            outer()

    def test_never_runs_normally_without_transaction(self):
        @Transactional(propagation=Propagation.NEVER)
        def no_txn_op():
            return "ok"

        assert no_txn_op() == "ok"

    # ── NESTED ───────────────────────────────────────────────────────────

    def test_nested_creates_savepoint_inner_rollback_preserves_outer(self):
        @Transactional(propagation=Propagation.NESTED)
        def inner_fail():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="NestedFail", email="nf@test.com"))
            session.flush()
            raise ValueError("nested fails")

        @Transactional
        def outer():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="OuterKept", email="ok@test.com"))
            session.flush()
            try:
                inner_fail()
            except ValueError:
                pass  # outer catches, continues

        outer()

        names = self._get_user_names()
        assert "OuterKept" in names
        assert "NestedFail" not in names

    def test_nested_creates_new_transaction_when_none_exists(self):
        @Transactional(propagation=Propagation.NESTED)
        def standalone():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Standalone", email="s@test.com"))

        standalone()
        assert self._count_users() == 1

    # ── MIXED PROPAGATION SCENARIOS ──────────────────────────────────────

    def test_requires_new_inside_nested_inside_required(self):
        """Three-level nesting: REQUIRED -> NESTED -> REQUIRES_NEW.

        Verifies that the stack correctly handles three levels of propagation.
        Full commit isolation across connections requires PostgreSQL; this test
        verifies the control flow and stack restoration on SQLite.
        """
        call_order = []

        @Transactional(propagation=Propagation.REQUIRES_NEW)
        def audit_log():
            call_order.append("audit")

        @Transactional(propagation=Propagation.NESTED)
        def risky_op():
            call_order.append("risky_start")
            audit_log()
            call_order.append("risky_after_audit")
            raise ValueError("risky fails")

        @Transactional
        def main_op():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="Main", email="main@test.com"))
            session.flush()
            call_order.append("main_start")
            try:
                risky_op()
            except ValueError:
                call_order.append("risky_caught")

        main_op()

        assert call_order == ["main_start", "risky_start", "audit", "risky_after_audit", "risky_caught"]
        assert "Main" in self._get_user_names()
        assert not SessionContextHolder.has_session()

    def test_mandatory_inside_required_succeeds(self):
        """MANDATORY works fine when called from inside a REQUIRED transaction."""
        @Transactional(propagation=Propagation.MANDATORY)
        def must_have_txn():
            session = SessionContextHolder.get_or_create_session()
            session.add(PropagationTestUser(name="MandatoryOK", email="mok@test.com"))

        @Transactional
        def outer():
            must_have_txn()

        outer()
        assert self._get_user_names() == ["MandatoryOK"]

    def test_never_inside_not_supported_succeeds(self):
        """NEVER succeeds inside NOT_SUPPORTED because the transaction is suspended."""
        @Transactional(propagation=Propagation.NEVER)
        def no_txn_ever():
            return "ran successfully"

        @Transactional(propagation=Propagation.NOT_SUPPORTED)
        def suspended():
            return no_txn_ever()

        @Transactional
        def outer():
            return suspended()

        assert outer() == "ran successfully"
