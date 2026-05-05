import pytest

from tests.shared.base_test_crud_repository_find_all_by_ids import (
    BaseFindAllByIds,
    FindByIdsUser,
    FindByIdsUserRepository,
)


@pytest.mark.postgres
class TestFindAllByIds(BaseFindAllByIds):
    pass
