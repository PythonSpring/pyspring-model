import pytest

from tests.shared.base_test_query_execution_service import (
    BaseQueryExecutionServiceParameterized,
    QESUser,
    QESUserRepository,
)


@pytest.mark.postgres
class TestQueryExecutionServiceParameterized(BaseQueryExecutionServiceParameterized):
    pass
