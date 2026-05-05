import pytest

from tests.shared.base_test_session_depth import (
    BaseSessionDepthWithStack,
)


@pytest.mark.postgres
class TestSessionDepthWithStack(BaseSessionDepthWithStack):
    pass
