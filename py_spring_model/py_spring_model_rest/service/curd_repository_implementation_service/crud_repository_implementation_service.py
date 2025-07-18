import copy
from typing import (
    Any,
    Callable,
    ClassVar,
    Type,
    TypeVar,
    Union,
    ParamSpec
)

from loguru import logger
from py_spring_core import Component
from pydantic import BaseModel
from enum import Enum
from sqlalchemy import ColumnElement
from sqlalchemy.sql import and_, or_
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.repository.crud_repository import CrudRepository
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
)

PySpringModelT = TypeVar("PySpringModelT", bound=PySpringModel)


class ConditionNotation(str,Enum):
    AND = "_and_"
    OR = "_or_"

class CrudRepositoryImplementationService(Component):
    """
    The `CrudRepositoryImplementationService` class is responsible for implementing the query logic for the `CrudRepository` inheritors.
    It dynamically generates wrapper methods for the additional methods (those starting with `get_by`, `find_by`, `get_all_by`, or `find_all_by`) defined in the `CrudRepository` inheritors. These wrapper methods handle the required field validation and execute the dynamically built queries using the `find_by` method.
    The `find_by` method dynamically builds a query based on the provided conditions and field values, and executes the query using the SQLModel session.
    It supports both single-result and multi-result queries.
    """

    skip_functions: ClassVar[set[str]] = set()


    @classmethod
    def add_skip_function(cls, func_name: str) -> None:
        cls.skip_functions.add(func_name)

    def __init__(self) -> None:
        self.basic_crud_methods = dir(CrudRepository)

    def get_all_crud_repository_inheritors(self) -> list[Type[CrudRepository]]:
        inheritors: list[Type[CrudRepository]] = []
        for _cls in set(CrudRepository.__subclasses__()):
            inheritors.append(_cls)
        return inheritors

    def _get_additional_methods(self, crud_repository: Type[CrudRepository]) -> list[str]:
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

    def _implemenmt_query(self, repository_type: Type[CrudRepository]) -> None:
        methods = self._get_additional_methods(repository_type)
        for method in methods:
            func_name = f"{repository_type.__name__}.{method}"
            if func_name in self.skip_functions:
                logger.info(
                    f"Skipping method: {func_name}, as it is marked as Query method."
                )
                continue

            query_builder = _MetodQueryBuilder(method)
            query = query_builder.parse_query()
            logger.debug(f"Method: {method} has query: {query}")

            _, model_type = repository_type._get_model_id_type_with_class()
            current_func = getattr(repository_type, method)

            copy_annotations: dict[str, Any] = copy.deepcopy(
                current_func.__annotations__
            )
            RETURN_KEY = "return"
            if RETURN_KEY in copy_annotations:
                copy_annotations.pop(RETURN_KEY)

            if len(copy_annotations) != len(query.required_fields) or set(
                copy_annotations.keys()
            ) != set(query.required_fields):
                raise ValueError(
                    f"Invalid number of annotations. Expected {query.required_fields}, received {list(copy_annotations.keys())}."
                )
            # Create a wrapper for the current method and query
            wrapped_method = self.create_implementation_wrapper(query, model_type, copy_annotations)
            logger.info(
                f"Binding method: {method} to {repository_type}, with query: {query}"
            )
            setattr(repository_type, method, wrapped_method)

    def create_implementation_wrapper(self, query: _Query, model_type: Type[PySpringModel], original_func_annotations: dict[str, Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            if len(query.required_fields) > 0:
                # Check if all required fields are present in kwargs
                if set(query.required_fields) != set(kwargs.keys()):
                    raise ValueError(
                        f"Invalid number of keyword arguments. Expected {query.required_fields}, received {kwargs}."
                    )

            # Execute the query
            sql_statement = self._get_sql_statement(model_type, query, kwargs)
            result = self._session_execute(sql_statement, query.is_one_result)
            logger.info(f"Executing query with params: {kwargs}")
            return result

        wrapper.__annotations__ = original_func_annotations
        return wrapper
    
    def _get_sql_statement(
        self,
        model_type: Type[PySpringModelT],
        parsed_query: _Query,
        params: dict[str, Any],
    ) -> SelectOfScalar[PySpringModelT]:
        filter_condition_stack: list[ColumnElement[bool]] = []
        
        for field in parsed_query.required_fields:
            column = getattr(model_type, field)
            param_value = params[field]
            
            # Check if this field has a specific operation
            if field in parsed_query.field_operations:
                operation = parsed_query.field_operations[field]
                if operation == "in":
                    # Handle IN operation
                    if not isinstance(param_value, (list, tuple, set)):
                        raise ValueError(f"Parameter for IN operation must be a collection (list, tuple, or set), got {type(param_value)}")
                    
                    # Handle empty list case - return no results
                    if len(param_value) == 0:
                        # Create a condition that's always false
                        filter_condition_stack.append(column == None)
                        continue
                    
                    filter_condition_stack.append(column.in_(param_value))
                else:
                    # Default to equality for unknown operations
                    filter_condition_stack.append(column == param_value)
            else:
                # Default equality operation
                filter_condition_stack.append(column == param_value)
        
        for notation in parsed_query.notations:
            right_condition = filter_condition_stack.pop(0)
            left_condition = filter_condition_stack.pop(0)
            match notation:
                case ConditionNotation.AND:
                    filter_condition_stack.append(and_(left_condition, right_condition))
                case ConditionNotation.OR:
                    filter_condition_stack.append(or_(left_condition, right_condition))

        query = select(model_type)
        if len(filter_condition_stack) > 0:
            query = query.where(filter_condition_stack.pop())
        return query
    
    @Transactional
    def _session_execute(self, statement: SelectOfScalar, is_one_result: bool) -> Any:
        session = SessionContextHolder.get_or_create_session()
        logger.debug(f"Executing query: \n{str(statement)}")
        result = (
            session.exec(statement).first()
            if is_one_result
            else session.exec(statement).fetchall()
        )
        return result

    def post_construct(self) -> None:
        for crud_repository in self.get_all_crud_repository_inheritors():
            self._implemenmt_query(crud_repository)

P = ParamSpec("P")
T = TypeVar("T", bound=BaseModel)
RT = TypeVar("RT", bound=Union[T, None, list[T]])  # type: ignore



def SkipAutoImplmentation(func: Callable[P, RT]) -> Callable[P, RT]:
    """
    Decorator to skip the auto implementation for a method.
    The method will not be implemented automatically by the `CrudRepositoryImplementationService`.
    The method should have the following signature:
    ```python
    @SkipAutoImplmentation
    def get_user_by_email(self, email: str) -> Optional[UserRead]:
        ...
    ```
    """
    func_name = func.__qualname__
    logger.info(f"Skipping auto implementation for function: {func_name}")
    CrudRepositoryImplementationService.add_skip_function(func_name)
    return func