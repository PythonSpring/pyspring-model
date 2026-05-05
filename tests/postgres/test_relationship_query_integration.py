import pytest

from tests.shared.base_test_relationship_query_integration import (
    BaseRelationshipQueryIntegration,
    Department,
    DepartmentRepository,
    Employee,
    EmployeeRepository,
)


@pytest.mark.postgres
class TestRelationshipQueryIntegration(BaseRelationshipQueryIntegration):
    pass
