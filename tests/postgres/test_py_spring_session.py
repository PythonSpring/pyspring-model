import pytest

from tests.shared.base_test_py_spring_session import (
    BasePySpringSessionAdd,
    BasePySpringSessionCommit,
    BasePySpringSessionRefresh,
    SessionUser,
)


@pytest.mark.postgres
class TestPySpringSessionAdd(BasePySpringSessionAdd):
    pass


@pytest.mark.postgres
class TestPySpringSessionRefresh(BasePySpringSessionRefresh):
    pass


@pytest.mark.postgres
class TestPySpringSessionCommit(BasePySpringSessionCommit):
    pass
