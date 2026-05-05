from tests.shared.base_test_integration_query_execution import (
    BaseCountExistsDeleteWithFieldOperations,
    BaseGetByPrefix,
    BaseIsNullIsNotNull,
    FieldOpQueryRepository,
    NullCheckUser,
    NullCheckUserRepository,
    OpUser,
    PrefixUser,
    PrefixUserRepository,
)


class TestIsNullIsNotNull(BaseIsNullIsNotNull):
    pass


class TestCountExistsDeleteWithFieldOperations(BaseCountExistsDeleteWithFieldOperations):
    pass


class TestGetByPrefix(BaseGetByPrefix):
    pass
