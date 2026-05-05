import pytest

from tests.shared.base_test_py_spring_model_rest_controller import (
    BasePostConstructConditionalRegistration,
    BasePySpringModelRestController,
    BaseRegisterBasicCrudRoutesRouterAssertion,
    CtrlUser,
)


@pytest.mark.postgres
class TestPySpringModelRestController(BasePySpringModelRestController):
    pass


@pytest.mark.postgres
class TestPostConstructConditionalRegistration(BasePostConstructConditionalRegistration):
    pass


@pytest.mark.postgres
class TestRegisterBasicCrudRoutesRouterAssertion(BaseRegisterBasicCrudRoutesRouterAssertion):
    pass
