from tests.shared.base_test_rest_controller_route_handlers import (
    BaseCreateRequestModel,
    BaseOpenAPISchemaGeneration,
    BaseParseId,
    BaseRestControllerRouteHandlers,
    RCHandlerUser,
)


class TestParseId(BaseParseId):
    pass


class TestCreateRequestModel(BaseCreateRequestModel):
    pass


class TestOpenAPISchemaGeneration(BaseOpenAPISchemaGeneration):
    pass


class TestRestControllerRouteHandlers(BaseRestControllerRouteHandlers):
    pass
