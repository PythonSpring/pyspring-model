
from typing import Any, Type
from fastapi import Response, status
from py_spring_core import RestController
from pydantic import BaseModel
from py_spring_model.core.model import PySpringModel
from py_spring_model.spring_model_rest.service.py_spring_model_rest_service import PySpringModelRestService




class PySpringModelRestController(RestController):
    """
    Represents a PySpring model REST controller, which is a subclass of PySpring
    """
    rest_service: PySpringModelRestService
    

    def register_routes(self) -> None:
        self._register_resource_for_models()
        
    def _register_resource_for_models(self) -> None:
        all_models = self.rest_service.get_all_models()
        for resource_name, model in all_models.items():
            self._register_basic_crud_routes(resource_name, model)

    def _register_basic_crud_routes(self, resource_name: str, model: Type[PySpringModel]) -> None:
        @self.router.get(
        f"/{resource_name}/{{id}}",
        summary=f"Get {resource_name} by ID",
        description=f"Retrieve a single {resource_name} by its unique identifier.",
        tags=[resource_name],
    )
        def get(id: int):
            return self.rest_service.get(model, id)

        @self.router.get(
            f"/{resource_name}/{{limit}}/{{offset}}",
            summary=f"Get All {resource_name}",
            description=f"Retrieve a paginated list of {resource_name} with the specified limit and offset.",
            tags=[resource_name],
        )
        def get_all(limit: int, offset: int):
            return self.rest_service.get_all(model, limit, offset)

        @self.router.post(
            f"/{resource_name}",
            summary=f"Get Multiple {resource_name} by IDs",
            description=f"Retrieve multiple {resource_name} by a list of their IDs.",
            tags=[resource_name],
        )

        class PostBody(BaseModel):
            ids: list[int]

        @self.router.post(
            f"/{resource_name}/ids",
            summary=f"Get Multiple {resource_name} by IDs",
            description=f"Retrieve multiple {resource_name} by a list of their IDs.",
            tags=[resource_name],
        )
        def get_all_by_ids(body: PostBody):
            return self.rest_service.get_all_by_ids(model, body.ids)

        @self.router.post(
            f"/{resource_name}",
            summary=f"Create a New {resource_name}",
            description=f"Create a new {resource_name} with the provided data.",
            tags=[resource_name],
        )
        def post(model: dict[str, Any]):
            model_type = self.rest_service.get_all_models()[resource_name]
            try:
                current_model = model_type.model_validate(model)
                return self.rest_service.create(current_model)
            except Exception as error:
                return Response(status_code=status.HTTP_400_BAD_REQUEST, content=str(error))

        @self.router.put(
            f"/{resource_name}/{{id}}",
            summary=f"Update {resource_name} by ID",
            description=f"Update an existing {resource_name} by its unique identifier.",
            tags=[resource_name],
        )
        def put(id: int, model: dict[str, Any]):
            model_type = self.rest_service.get_all_models()[resource_name]
            try:
                current_model = model_type.model_validate(model)
                return self.rest_service.update(id, current_model)
            except Exception as error:
                return Response(status_code=status.HTTP_400_BAD_REQUEST, content=str(error))

        @self.router.delete(
            f"/{resource_name}/{{id}}",
            summary=f"Delete {resource_name} by ID",
            description=f"Delete a {resource_name} by its unique identifier.",
            tags=[resource_name],
        )
        def delete(id: int) -> Response:
            self.rest_service.delete(model, id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)




