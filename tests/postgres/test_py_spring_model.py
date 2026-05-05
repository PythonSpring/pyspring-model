import pytest

from tests.shared.base_test_py_spring_model import (
    BasePySpringModel,
    SampleModel,
)


@pytest.mark.postgres
class TestPySpringModel(BasePySpringModel):
    pass
