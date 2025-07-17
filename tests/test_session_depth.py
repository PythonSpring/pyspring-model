import pytest
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.core.model import PySpringModel


class TestSessionDepth:
    """Test the explicit session depth tracking functionality"""

    def setup_method(self):
        """Clean up any existing sessions before each test"""
        SessionContextHolder.clear_session()

    def teardown_method(self):
        """Clean up after each test"""
        SessionContextHolder.clear_session()

    def test_session_depth_starts_at_zero(self):
        """Test that session depth starts at 0"""
        assert SessionContextHolder.get_session_depth() == 0

    def test_session_depth_increments_and_decrements(self):
        """Test that session depth properly increments and decrements"""
        # Initially 0
        assert SessionContextHolder.get_session_depth() == 0
        
        # Enter first level
        depth1 = SessionContextHolder.enter_session()
        assert depth1 == 1
        assert SessionContextHolder.get_session_depth() == 1
        
        # Enter second level
        depth2 = SessionContextHolder.enter_session()
        assert depth2 == 2
        assert SessionContextHolder.get_session_depth() == 2
        
        # Exit second level
        depth_after_exit1 = SessionContextHolder.exit_session()
        assert depth_after_exit1 == 1
        assert SessionContextHolder.get_session_depth() == 1
        
        # Exit first level
        depth_after_exit2 = SessionContextHolder.exit_session()
        assert depth_after_exit2 == 0
        assert SessionContextHolder.get_session_depth() == 0

    def test_session_cleared_only_at_outermost_level(self):
        """Test that session is only cleared when depth reaches 0"""
        # Enter first level and create session
        SessionContextHolder.enter_session()
        session = SessionContextHolder.get_or_create_session()
        assert SessionContextHolder.has_session()
        
        # Enter second level - session should still exist
        SessionContextHolder.enter_session()
        assert SessionContextHolder.has_session()
        assert SessionContextHolder.get_session_depth() == 2
        
        # Exit second level - session should still exist
        SessionContextHolder.exit_session()
        assert SessionContextHolder.has_session()
        assert SessionContextHolder.get_session_depth() == 1
        
        # Exit first level - session should be cleared
        SessionContextHolder.exit_session()
        assert not SessionContextHolder.has_session()
        assert SessionContextHolder.get_session_depth() == 0

    def test_clear_session_resets_depth(self):
        """Test that clear_session() resets the depth to 0"""
        SessionContextHolder.enter_session()
        SessionContextHolder.enter_session()
        assert SessionContextHolder.get_session_depth() == 2
        
        SessionContextHolder.clear_session()
        assert SessionContextHolder.get_session_depth() == 0

    @pytest.mark.parametrize("nesting_levels", [1, 2, 3, 5])
    def test_transactional_depth_tracking(self, nesting_levels):
        """Test that @Transactional properly tracks depth at various nesting levels"""
        depth_records = []
        
        def create_nested_function(level: int):
            @Transactional
            def nested_func():
                current_depth = SessionContextHolder.get_session_depth()
                depth_records.append(current_depth)
                if level > 1:
                    create_nested_function(level - 1)()
            return nested_func
        
        # Create and execute nested function
        outermost_func = create_nested_function(nesting_levels)
        outermost_func()
        
        # Verify depth progression
        assert len(depth_records) == nesting_levels
        for i, recorded_depth in enumerate(depth_records):
            expected_depth = i + 1
            assert recorded_depth == expected_depth, f"At level {i+1}, expected depth {expected_depth}, got {recorded_depth}"
        
        # Verify session is cleaned up
        assert SessionContextHolder.get_session_depth() == 0
        assert not SessionContextHolder.has_session()

    def test_depth_prevents_negative_values(self):
        """Test that depth counter prevents going below 0"""
        assert SessionContextHolder.get_session_depth() == 0
        
        # Try to exit when already at 0
        new_depth = SessionContextHolder.exit_session()
        assert new_depth == 0
        assert SessionContextHolder.get_session_depth() == 0 