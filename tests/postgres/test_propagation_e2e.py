import pytest

from tests.shared.base_test_propagation_e2e import (
    BasePropagationE2E,
    PropagationTestUser,
)


@pytest.mark.postgres
class TestPropagationE2E(BasePropagationE2E):
    pass
