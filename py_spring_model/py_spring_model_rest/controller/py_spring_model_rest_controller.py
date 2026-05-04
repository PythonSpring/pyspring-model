from typing import Any, Type, Union
from loguru import logger

from fastapi import Response, status
from py_spring_core import RestController
from pydantic import BaseModel, create_model

from py_spring_model.core.commons import PySpringModelProperties
from py_spring_model.core.model import PySpringModel
from py_spring_model.py_spring_model_rest.service.py_spring_model_rest_service import (
    PySpringModelRestService,
)


class PySpringModelRestController(RestController):
    """
    Represents a PySpring model REST controller providing auto-generated CRUD routes.
    """

    rest_service: PySpringModelRestService
    properties: PySpringModelProperties

    def post_construct(self) -> None:
        if self.properties.create_crud_routes:
            logger.info("[CRUD ROUTE REGISTRATION] Registering CRUD routes for all models.")
            self._register_resource_for_models()

    def _register_resource_for_models(self) -> None:
        all_models = self.rest_service.get_all_models()
        for resource_name, model in all_models.items():
            self._register_basic_crud_routes(resource_name, model)

    @staticmethod
    def _create_request_model(model: Type[PySpringModel]) -> Type[BaseModel]:
        fields = {}
        for name, field_info in model.model_fields.items():
            fields[name] = (field_info.annotation, field_info)
        return create_model(f"{model.__name__}Input", **fields)

    def _register_basic_crud_routes(
        self, resource_name: str, model: Type[PySpringModel]
    ) -> None:
        assert self.router is not None, "Router must be initialized before registering routes."
        request_model = self._create_request_model(model)

        @self.router.get(
            f"/{resource_name}/count",
            summary=f"Count {resource_name}",
            description=f"Get the total count of {resource_name}.",
            tags=[resource_name],
        )
        def count():
            return self.rest_service.count(model)

        @self.router.get(
            f"/{resource_name}/{{id}}",
            summary=f"Get {resource_name} by ID",
            description=f"Retrieve a single {resource_name} by its unique identifier.",
            tags=[resource_name],
        )
        def get(id: Union[int, str]):
            parsed_id = self._parse_id(id, model)
            return self.rest_service.get(model, parsed_id)

        @self.router.get(
            f"/{resource_name}/{{limit}}/{{offset}}",
            summary=f"Get All {resource_name}",
            description=f"Retrieve a paginated list of {resource_name} with the specified limit and offset.",
            tags=[resource_name],
        )
        def get_all(limit: int, offset: int):
            return self.rest_service.get_all(model, limit, offset)

        class PostIdsBody(BaseModel):
            ids: list[Union[int, str]]

        @self.router.post(
            f"/{resource_name}/ids",
            summary=f"Get Multiple {resource_name} by IDs",
            description=f"Retrieve multiple {resource_name} by a list of their IDs.",
            tags=[resource_name],
        )
        def get_all_by_ids(body: PostIdsBody):
            parsed_ids = [self._parse_id(id_val, model) for id_val in body.ids]
            return self.rest_service.get_all_by_ids(model, parsed_ids)

        @self.router.post(
            f"/{resource_name}",
            summary=f"Create a New {resource_name}",
            description=f"Create a new {resource_name} with the provided data.",
            tags=[resource_name],
        )
        def post(model_data: request_model):  # type: ignore[valid-type]
            try:
                current_model = model.model_validate(model_data.model_dump(exclude_unset=True))
                return self.rest_service.create(current_model)
            except Exception as error:
                return Response(
                    status_code=status.HTTP_400_BAD_REQUEST, content=str(error)
                )

        @self.router.post(
            f"/{resource_name}/batch",
            summary=f"Batch Create {resource_name}",
            description=f"Create multiple {resource_name} at once.",
            tags=[resource_name],
        )
        def batch_create(models: list[request_model]):  # type: ignore[valid-type]
            validated = [model.model_validate(m.model_dump(exclude_unset=True)) for m in models]
            return self.rest_service.batch_create(validated)

        @self.router.put(
            f"/{resource_name}/{{id}}",
            summary=f"Update {resource_name} by ID",
            description=f"Update an existing {resource_name} by its unique identifier.",
            tags=[resource_name],
        )
        def put(id: Union[int, str], model_data: request_model):  # type: ignore[valid-type]
            parsed_id = self._parse_id(id, model)
            try:
                current_model = model.model_validate(model_data.model_dump(exclude_unset=True))
                return self.rest_service.update(parsed_id, current_model)
            except Exception as error:
                return Response(
                    status_code=status.HTTP_400_BAD_REQUEST, content=str(error)
                )

        @self.router.delete(
            f"/{resource_name}/{{id}}",
            summary=f"Delete {resource_name} by ID",
            description=f"Delete a {resource_name} by its unique identifier.",
            tags=[resource_name],
        )
        def delete(id: Union[int, str]) -> Response:
            parsed_id = self._parse_id(id, model)
            self.rest_service.delete(model, parsed_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        class BatchDeleteBody(BaseModel):
            ids: list[Union[int, str]]

        @self.router.delete(
            f"/{resource_name}/batch",
            summary=f"Batch Delete {resource_name}",
            description=f"Delete multiple {resource_name} by their IDs.",
            tags=[resource_name],
        )
        def batch_delete(body: BatchDeleteBody):
            parsed_ids = [self._parse_id(id_val, model) for id_val in body.ids]
            self.rest_service.batch_delete(model, parsed_ids)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _parse_id(id_value: Union[int, str], model: Type[PySpringModel]) -> Any:
        """Parse an ID value to the appropriate type based on the model's ID field."""
        from uuid import UUID
        id_annotation = model.__annotations__.get("id")
        if id_annotation is int:
            return int(id_value)
        if id_annotation is UUID:
            return UUID(str(id_value)) if not isinstance(id_value, UUID) else id_value
        return id_value
