import pytest

from tests.shared.base_test_e2e_py_spring_model_provider import (
    BaseDuplicateModelImport,
    BasePySpringModelStarterEdgeCases,
    BasePySpringModelStarterPostgres,
    BasePySpringModelStarterSQLite,
    Category,
    CategoryRepository,
    Item,
    ItemRepository,
)


@pytest.mark.postgres
class TestPySpringModelStarterSQLite(BasePySpringModelStarterSQLite):
    pass


@pytest.mark.postgres
class TestPySpringModelStarterEdgeCases(BasePySpringModelStarterEdgeCases):
    pass


@pytest.mark.postgres
class TestPySpringModelStarterPostgres(BasePySpringModelStarterPostgres):
    pass


@pytest.mark.postgres
class TestDuplicateModelImport(BaseDuplicateModelImport):
    pass
