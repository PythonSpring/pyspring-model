from typing import Any, Type

from loguru import logger
from py_spring_core import Component
from sqlalchemy import ColumnElement
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
                        f"Executing query: {query}: {kwargs}"
                    )
                    # Execute the query
                    result = service.find_by(
                        model_type=model_type,
                        parsed_query=query,
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
        parsed_query: Query,
        **kwargs,
    ) -> Any:
        """
        Executes a query based on the provided conditions and field values.    
        Args:
            model_type (Type[SQLModel]): The SQLModel class to query.
            parsed_query (Query): The parsed query object containing the required fields and notations.
            **kwargs: Additional keyword arguments to filter the query.
        Returns:
            Any: The result of the executed query, either a single result or a list of results.
        """

        filter_condition_stack: list[ColumnElement[bool]] = [
            getattr(model_type, field) == kwargs[field]
            for field in parsed_query.required_fields
        ]
        for notation in parsed_query.notations:
            left_condition = filter_condition_stack.pop(0)
            right_condition = filter_condition_stack.pop(0)
            match notation:
                case "_and_":
                    filter_condition_stack.append(
                        and_(left_condition, right_condition)
                    )
                case "_or_":
                    filter_condition_stack.append(
                        or_(left_condition, right_condition)
                    )
        
        query = select(model_type)
        if len(filter_condition_stack) > 0:
            query = query.where(filter_condition_stack.pop())

        with PySpringModel.create_session() as session:
            logger.debug(f"Executing query: \n{str(query)}")
            if parsed_query.is_one_result:
                result = session.exec(query).first()
            else:
                result = session.exec(query).fetchall()
        return result

    def post_construct(self) -> None:
        for crud_repository in self.get_all_crud_repository_inheritors():
            self._implemenmt_query(crud_repository)
