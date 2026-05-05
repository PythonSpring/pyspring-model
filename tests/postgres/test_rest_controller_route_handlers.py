import pytest

from tests.shared.base_test_rest_controller_route_handlers import (
    BaseCreateRequestModel,
    BaseOpenAPISchemaGeneration,
    BaseParseId,
    BaseRestControllerRouteHandlers,
    RCHandlerUser,
)


@pytest.mark.postgres
class TestParseId(BaseParseId):
    pass


@pytest.mark.postgres
class TestCreateRequestModel(BaseCreateRequestModel):
    pass


@pytest.mark.postgres
class TestOpenAPISchemaGeneration(BaseOpenAPISchemaGeneration):
    pass


@pytest.mark.postgres
class TestRestControllerRouteHandlers(BaseRestControllerRouteHandlers):
    pass
