import pytest

from tests.shared.base_test_query_execution_service_return_types import (
    BaseQueryExecutionServiceInvalidReturnType,
    BaseQueryExecutionServiceMissingAnnotation,
    BaseQueryReturnTypes,
    ReturnTypeUser,
    ReturnTypeUserRepository,
)


@pytest.mark.postgres
class TestQueryReturnTypes(BaseQueryReturnTypes):
    pass


@pytest.mark.postgres
class TestQueryExecutionServiceInvalidReturnType(BaseQueryExecutionServiceInvalidReturnType):
    pass


@pytest.mark.postgres
class TestQueryExecutionServiceMissingAnnotation(BaseQueryExecutionServiceMissingAnnotation):
    pass
