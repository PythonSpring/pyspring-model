from tests.shared.base_test_query_execution_service_return_types import (
    BaseQueryExecutionServiceInvalidReturnType,
    BaseQueryExecutionServiceMissingAnnotation,
    BaseQueryReturnTypes,
    ReturnTypeUser,
    ReturnTypeUserRepository,
)


class TestQueryReturnTypes(BaseQueryReturnTypes):
    pass


class TestQueryExecutionServiceInvalidReturnType(BaseQueryExecutionServiceInvalidReturnType):
    pass


class TestQueryExecutionServiceMissingAnnotation(BaseQueryExecutionServiceMissingAnnotation):
    pass
