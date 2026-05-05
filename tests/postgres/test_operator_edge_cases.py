import pytest

from tests.shared.base_test_operator_edge_cases import (
    BaseOperatorInLike,
    BaseOperatorInLikeRelationship,
)


@pytest.mark.postgres
class TestOperatorInLike(BaseOperatorInLike):
    pass


@pytest.mark.postgres
class TestOperatorInLikeRelationship(BaseOperatorInLikeRelationship):
    pass
