import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, TransactionState, Transactional


class TestSessionDepthWithStack:
    """Test depth tracking through the stack-based TransactionState."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        SessionContextHolder.clear()
        yield
        SessionContextHolder.clear()
        PySpringModel._engine = None
        PySpringModel._metadata = None
        PySpringModel._connection = None

    def test_no_state_initially(self):
        assert SessionContextHolder.current_state() is None

    def test_depth_increments_on_join(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)
        assert state.depth == 1
        state.depth += 1
        assert state.depth == 2
        state.depth -= 1
        assert state.depth == 1

    def test_stack_cleared_after_outermost_pop(self):
        state = TransactionState(session=MagicMock(), depth=1)
        SessionContextHolder.push_state(state)
        SessionContextHolder.pop_state()
        assert SessionContextHolder.current_state() is None

    def test_clear_resets_everything(self):
        s1 = MagicMock()
        s2 = MagicMock()
        SessionContextHolder.push_state(TransactionState(session=s1, depth=1))
        SessionContextHolder.push_state(TransactionState(session=s2, depth=1))
        SessionContextHolder.clear()
        assert SessionContextHolder.current_state() is None

    @pytest.mark.parametrize("nesting_levels", [1, 2, 3, 5])
    def test_transactional_depth_tracking(self, nesting_levels):
        """@Transactional with REQUIRED semantics tracks depth correctly at various nesting levels."""
        depth_records = []

        def create_nested_function(level: int):
            @Transactional
            def nested_func():
                state = SessionContextHolder.current_state()
                depth_records.append(state.depth)
                if level > 1:
                    create_nested_function(level - 1)()
            return nested_func

        outermost_func = create_nested_function(nesting_levels)
        outermost_func()

        assert len(depth_records) == nesting_levels
        for i, recorded_depth in enumerate(depth_records):
            expected_depth = i + 1
            assert recorded_depth == expected_depth, (
                f"At level {i+1}, expected depth {expected_depth}, got {recorded_depth}"
            )
        assert SessionContextHolder.current_state() is None
