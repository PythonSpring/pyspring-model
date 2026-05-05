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


class TestPySpringModelStarterSQLite(BasePySpringModelStarterSQLite):
    pass


class TestPySpringModelStarterEdgeCases(BasePySpringModelStarterEdgeCases):
    pass


class TestPySpringModelStarterPostgres(BasePySpringModelStarterPostgres):
    pass


class TestDuplicateModelImport(BaseDuplicateModelImport):
    pass
