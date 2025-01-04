from typing import Any, Type

from loguru import logger
from py_spring_core import Component
from sqlalchemy.sql import and_, or_
from sqlmodel import SQLModel, select

from py_spring_model.core.model import PySpringModel
from py_spring_model.repository.crud_repository import CrudRepository
from py_spring_model.spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    MetodQueryBuilder,
    Query,
)


class CrudRepositoryImplementationService(Component):
    """
    The `CrudRepositoryImplementationService` class is responsible for implementing the query logic for the `CrudRepository` inheritors.
    It dynamically generates wrapper methods for the additional methods (those starting with `get_by`, `find_by`, `get_all_by`, or `find_all_by`) defined in the `CrudRepository` inheritors. These wrapper methods handle the required field validation and execute the dynamically built queries using the `find_by` method.
    The `find_by` method dynamically builds a query based on the provided conditions and field values, and executes the query using the SQLModel session.
    It supports both single-result and multi-result queries.
    """

    def __init__(self) -> None:
        self.basic_crud_methods = dir(CrudRepository)

    def get_all_crud_repository_inheritors(self) -> list[Type[CrudRepository]]:
        inheritors: list[Type[CrudRepository]] = []
        for _cls in set(CrudRepository.__subclasses__()):
            inheritors.append(_cls)
        return inheritors

    def _get_addition_methods(self, crud_repository: Type[CrudRepository]) -> list[str]:
        return [
            method_name
            for method_name in dir(crud_repository)
            if not method_name.startswith("__")
            and method_name not in self.basic_crud_methods
            and callable(getattr(crud_repository, method_name))
            and (
                method_name.startswith("get_by")
                or method_name.startswith("find_by")
                or method_name.startswith("get_all_by")
                or method_name.startswith("find_all_by")
            )
        ]

    def _implemenmt_query(self, repository_type: Type[CrudRepository]) -> Any:
        methods = self._get_addition_methods(repository_type)
        for method in methods:
            query_builder = MetodQueryBuilder(method)
            query = query_builder.parse_query()
            logger.debug(f"Method: {method} has query: {query}")

            _id, model_type = repository_type._get_model_id_type_with_class()
            current_func = getattr(repository_type, method)

            def create_wrapper(
                service: "CrudRepositoryImplementationService", query: Query
            ) -> Any:
                def wrapper(*args, **kwargs) -> Any:
                    if len(query.required_fields) > 0:
                        for field in query.required_fields:
                            if field in kwargs:
                                continue
                            raise ValueError(f"Missing required field: {field}")

                    for key, value in kwargs.items():
                        if value is None:
                            raise ValueError(
                                f"Invalid field name: {key}, received None value."
                            )

                    logger.info(
                        f"Executing query condition: {query.conditions}, is_one_result={query.is_one_result}: {kwargs}"
                    )
                    # Execute the query
                    result = service.find_by(
                        model_type=model_type,
                        conditions=query.conditions,
                        is_one_result=query.is_one_result,
                        **kwargs,
                    )
                    return result

                wrapper.__annotations__ = current_func.__annotations__
                return wrapper

            # Create a wrapper for the current method and query
            wrapped_method = create_wrapper(self, query)
            # Bind the wrapper as a method to the repository_type
            logger.info(
                f"Binding method: {method} to {repository_type}, with query: {query}"
            )
            setattr(
                repository_type,
                method,
                wrapped_method.__get__(repository_type, repository_type.__class__),
            )

    def find_by(
        self,
        model_type: Type[SQLModel],
        conditions: list[str],
        is_one_result: bool,
        **kwargs,
    ) -> Any:
        """
        Dynamically builds a query based on fields and logical operators.
        :param model: The SQLModel class representing the table.
        :param conditions: A list of field names and logical operators.
        :param kwargs: The field values to filter the query.
        :return: Queryed result from the database.
        """
        filters = []
        operator = and_  # Default logical operator

        for cond in conditions:
            if cond == "_and_":
                operator = and_
            elif cond == "_or_":
                operator = or_
            else:
                current_query_field = cond
                filters.append(
                    getattr(model_type, cond) == kwargs.get(current_query_field)
                )
        # Combine filters with the operator
        if len(filters) > 0:
            query = select(model_type).where(operator(*filters))
        else:
            query = select(model_type)
        with PySpringModel.create_session() as session:
            logger.debug(f"Executing query: \n{str(query)}")
            if is_one_result:
                result = session.exec(query).first()
            else:
                result = session.exec(query).fetchall()
        return result

    def post_construct(self) -> None:
        for crud_repository in self.get_all_crud_repository_inheritors():
            self._implemenmt_query(crud_repository)
