import pytest

from tests.shared.base_test_py_spring_model_error_paths import (
    BasePySpringModelErrorPaths,
    ErrorPathModel,
)


@pytest.mark.postgres
class TestPySpringModelErrorPaths(BasePySpringModelErrorPaths):
    pass
