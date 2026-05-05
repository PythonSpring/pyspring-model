import pytest

from tests.shared.base_test_session_middleware import (
    BaseSessionControllerPostConstruct,
    BaseSessionMiddleware,
)


@pytest.mark.postgres
class TestSessionMiddleware(BaseSessionMiddleware):
    pass


@pytest.mark.postgres
class TestSessionControllerPostConstruct(BaseSessionControllerPostConstruct):
    pass
