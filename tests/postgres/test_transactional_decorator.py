import pytest

from tests.shared.base_test_transactional_decorator import (
    BaseTransactionalDecorator,
    TransactionalTestUser,
)


@pytest.mark.postgres
class TestTransactionalDecorator(BaseTransactionalDecorator):
    pass
