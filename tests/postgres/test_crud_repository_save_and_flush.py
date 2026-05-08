import pytest

from tests.shared.base_test_crud_repository_save_and_flush import (
    BaseCrudRepositorySaveAndFlush,
    SaveFlushUser,
    SaveFlushUserRepository,
)


@pytest.mark.postgres
class TestCrudRepositorySaveAndFlush(BaseCrudRepositorySaveAndFlush):
    pass
