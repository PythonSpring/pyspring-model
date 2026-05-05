import pytest

from tests.shared.base_test_repository_base import (
    BaseRepositoryBase,
    RepoItem,
    RepoItemView,
)


@pytest.mark.postgres
class TestRepositoryBase(BaseRepositoryBase):
    pass
