import pytest

from tests.shared.base_test_implementation_service_edge_cases import (
    BaseCastPluralToSingular,
    BaseGetAdditionalMethods,
    BaseWrapperUnknownParameter,
    EdgeCaseModel,
    EdgeCaseRepo,
    WrapperModel,
    WrapperRepo,
)


@pytest.mark.postgres
class TestCastPluralToSingular(BaseCastPluralToSingular):
    pass


@pytest.mark.postgres
class TestGetAdditionalMethods(BaseGetAdditionalMethods):
    pass


@pytest.mark.postgres
class TestWrapperUnknownParameter(BaseWrapperUnknownParameter):
    pass
