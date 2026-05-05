import pytest

from tests.shared.base_test_field_operations import (
    BaseFieldOperations,
    TestUser,
    TestUserRepository,
)


@pytest.mark.postgres
class TestFieldOperations(BaseFieldOperations):
    pass
