import copy
import functools
from collections.abc import Iterable
from typing import (
    Any,
    Callable,
    ClassVar,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    ParamSpec
)

from loguru import logger
from py_spring_core import Component
from pydantic import BaseModel
from sqlalchemy import ColumnElement, text
from sqlalchemy.sql import and_, or_
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from py_spring_model.core.model import PySpringModel
from py_spring_model.repository.crud_repository import CrudRepository
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
)

PySpringModelT = TypeVar("PySpringModelT", bound=PySpringModel)

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
        filter_condition_stack: list[ColumnElement[bool]] = [
            getattr(model_type, field) == params[field]
            for field in parsed_query.required_fields
        ]
        for notation in parsed_query.notations:
            right_condition = filter_condition_stack.pop(0)
            left_condition = filter_condition_stack.pop(0)
            match notation:
                case "_and_":
                    filter_condition_stack.append(and_(left_condition, right_condition))
                case "_or_":
                    filter_condition_stack.append(or_(left_condition, right_condition))

        query = select(model_type)
        if len(filter_condition_stack) > 0:
            query = query.where(filter_condition_stack.pop())
        return query
    
    def _session_execute(self, statement: SelectOfScalar, is_one_result: bool) -> Any:
        with PySpringModel.create_session() as session:
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

def Query(query_template: str) -> Callable[[Callable[P, RT]], Callable[P, RT]]:
    def decorator(func: Callable[P, RT]) -> Callable[P, RT]:
        func_full_name = func.__qualname__
        CrudRepositoryImplementationService.add_skip_function(func_full_name)
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> RT:
            nonlocal query_template
            RETURN = "return"

            annotations = func.__annotations__
            if RETURN not in annotations:
                raise ValueError(f"Missing return annotation for function: {func.__name__}")
            
            return_type = annotations[RETURN]
            for key, value_type in annotations.items():
                if key == RETURN:
                    continue
                if key not in kwargs or kwargs[key] is None:
                    raise ValueError(f"Missing required argument: {key}")
                if value_type != type(kwargs[key]):
                    raise TypeError(f"Invalid type for argument {key}. Expected {value_type}, got {type(kwargs[key])}")
            
            sql = query_template.format(**kwargs)
            with PySpringModel.create_session() as session:  # Replace with your actual session mechanism
                reutrn_origin = get_origin(return_type)
                return_args = get_args(return_type)


                # Handle None or list[T]
                if type(None) in return_args:
                    actual_type = [arg for arg in return_args if arg is not type(None)].pop()
                else:
                    if len(return_args) != 0:
                        actual_type = return_args[0]
                    else:
                        actual_type = return_type

                if reutrn_origin in {list, Iterable} and return_args:
                    if not issubclass(actual_type, BaseModel):
                        raise ValueError(f"Invalid return type: {return_type}, expected Iterable[BaseModel]")
                    
                    result = session.execute(text(sql)).fetchall()
                    return cast(RT, [actual_type.model_validate(row._asdict()) for row in result])
                
                elif issubclass(actual_type, BaseModel):
                    result = session.execute(text(sql)).first()
                    if result is None:
                        return cast(RT, None)
                    return cast(RT, actual_type.model_validate(result._asdict()))
                else:
                    raise ValueError(f"Invalid return type: {actual_type}") 
        return wrapper
    return decorator


def SkipAutoImplmentation(func: Callable[P, RT]) -> Callable[P, RT]:
    func_name = func.__qualname__
    logger.info(f"Skipping auto implementation for function: {func_name}")
    CrudRepositoryImplementationService.add_skip_function(func_name)
    return func