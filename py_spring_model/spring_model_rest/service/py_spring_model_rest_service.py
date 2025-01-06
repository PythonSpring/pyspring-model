from typing import Optional, Type, TypeVar
from uuid import UUID

from py_spring_core import Component

from py_spring_model import PySpringModel

ID = TypeVar("ID", int, UUID)
ModelT = TypeVar("ModelT", bound=PySpringModel)


class PySpringModelRestService(Component):
    """
    This class provides a REST service for interacting with PySpringModel instances. 
    It includes methods for: 
     1. Retrieving all available models, 
     2. Getting a single model by ID, 
     3. Getting multiple models by ID, getting a paginated list of models, 
     4. Creating a new model, 
     5. Updating an existing model, 
     6. Deleting a model by ID.
    """     
    def get_all_models(self) -> dict[str, type[PySpringModel]]:
        return PySpringModel.get_model_lookup()

    def get(self, model_type: Type[ModelT], id: ID) -> Optional[ModelT]:
        with PySpringModel.create_managed_session() as session:
            return session.get(model_type, id)  # type: ignore

    def get_all_by_ids(self, model_type: Type[ModelT], ids: list[ID]) -> list[ModelT]:
        with PySpringModel.create_managed_session() as session:
            return session.query(model_type).filter(model_type.id.in_(ids)).all()  # type: ignore

    def get_all(
        self, model_type: Type[ModelT], limit: int, offset: int
    ) -> list[ModelT]:
        with PySpringModel.create_managed_session() as session:
            return session.query(model_type).offset(offset).limit(limit).all()

    def create(self, model: ModelT) -> ModelT:
        with PySpringModel.create_managed_session() as session:
            session.add(model)
            return model

    def update(self, id: ID, model: ModelT) -> Optional[ModelT]:
        with PySpringModel.create_managed_session() as session:
            model_type = type(model)
            primary_keys = PySpringModel.get_primary_key_columns(model_type)
            optional_model = session.get(model_type, id)  # type: ignore
            if optional_model is None:
                return

            for key, value in model.model_dump().items():
                if key in primary_keys:
                    continue
                setattr(optional_model, key, value)
            session.add(optional_model)

    def delete(self, model_type: Type[ModelT], id: ID) -> None:
        with PySpringModel.create_managed_session() as session:
            session.query(model_type).filter(model_type.id == id).delete()  # type: ignore
            session.commit()
