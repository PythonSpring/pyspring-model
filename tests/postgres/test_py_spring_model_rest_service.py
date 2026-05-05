import pytest

from tests.shared.base_test_py_spring_model_rest_service import (
    BasePySpringModelRestService,
    RestUser,
)


@pytest.mark.postgres
class TestPySpringModelRestService(BasePySpringModelRestService):
    pass
