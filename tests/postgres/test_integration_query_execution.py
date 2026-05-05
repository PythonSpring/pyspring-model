import pytest

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


@pytest.mark.postgres
class TestIsNullIsNotNull(BaseIsNullIsNotNull):
    pass


@pytest.mark.postgres
class TestCountExistsDeleteWithFieldOperations(BaseCountExistsDeleteWithFieldOperations):
    pass


@pytest.mark.postgres
class TestGetByPrefix(BaseGetByPrefix):
    pass
