import pytest

from tests.shared.base_test_crud_repository import (
    BaseCrudRepository,
    User,
    UserRepository,
)


@pytest.mark.postgres
class TestCrudRepository(BaseCrudRepository):
    pass
