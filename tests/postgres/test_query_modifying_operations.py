import pytest

from tests.shared.base_test_query_modifying_operations import (
    BaseQueryModifyingOperations,
    TestUser,
    TestUserRepository,
)


@pytest.mark.postgres
class TestQueryModifyingOperations(BaseQueryModifyingOperations):
    pass
