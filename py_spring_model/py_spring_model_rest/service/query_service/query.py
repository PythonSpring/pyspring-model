import functools
from collections.abc import Iterable
from typing import (
    Any,
    Callable,
    Optional,
    ParamSpec,
    Type,
    TypeVar,
    cast,
    get_args,
    get_origin
)

from pydantic import BaseModel
from sqlalchemy import Row, text

from py_spring_model.core.model import PySpringModel
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import CrudRepositoryImplementationService

P = ParamSpec("P")
T = TypeVar("T", bound=BaseModel)
RT = TypeVar("RT")


class QueryExecutionService:
    @classmethod
    def execute_query(cls,
        query_template: str,
        func: Callable[P, RT],
        kwargs: dict,
        is_modifying: bool
    ) -> RT:
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
            expected_origin = get_origin(value_type) or value_type
            if not isinstance(kwargs[key], expected_origin):
                raise TypeError(f"Invalid type for argument {key}. Expected {value_type}, got {type(kwargs[key])}")

        with PySpringModel.create_managed_session(should_commit=is_modifying) as session:
            return_origin = get_origin(return_type)
            return_args = get_args(return_type)

            actual_type = cls._get_actual_type(return_args, return_type)
            is_optional = type(None) in return_args

            # None return type (DELETE/UPDATE without RETURNING)
            if return_type is type(None):
                session.execute(text(query_template), kwargs)
                return cast(RT, None)

            # Scalar return types (int, float, str, bool)
            if actual_type in (int, float, str, bool):
                result = session.execute(text(query_template), kwargs).scalar()
                if result is None and is_optional:
                    return cast(RT, None)
                return cast(RT, result)

            # Iterable of BaseModel
            if return_origin in {list, Iterable} and return_args:
                cls._validate_return_type(actual_type, return_type)
                result = session.execute(text(query_template), kwargs).fetchall()
                return cast(RT, [actual_type.model_validate(row._asdict()) for row in result])

            # Single BaseModel
            if issubclass(actual_type, BaseModel):
                result = session.execute(text(query_template), kwargs).first()
                if result is None:
                    if is_optional:
                        return cast(RT, None)
                    raise ValueError(f"No result found for query: {query_template}")
                return cast(RT, cls._process_single_result(result, actual_type))

            raise ValueError(f"Invalid return type: {actual_type}")

    @classmethod
    def _get_actual_type(cls, return_args: tuple[Type[Any]], return_type: Type[Any]) -> Type[Any]:
        if type(None) in return_args:
            return next(arg for arg in return_args if arg is not type(None))
        elif return_args:
            return return_args[0]
        else:
            return return_type

    @classmethod
    def _validate_return_type(cls, actual_type, return_type):
        if not issubclass(actual_type, BaseModel):
            raise ValueError(f"Invalid return type: {return_type}, expected Iterable[BaseModel]")

    @classmethod
    def _process_single_result(cls, result: Row, actual_type: Type[BaseModel]) -> Optional[BaseModel]:
        return actual_type.model_validate(result._asdict())


def Query(query_template: str, is_modifying: bool = False) -> Callable[[Callable[P, RT]], Callable[P, RT]]:
    """
    Decorator to mark a method as a query method.
    Template uses SQLAlchemy bindparam syntax (:param).

    Example:
    ```python
    @Query("SELECT * FROM users WHERE email = :email")
    def get_user_by_email(self, email: str) -> Optional[UserRead]:
        ...
    ```
    """
    def decorator(func: Callable[P, RT]) -> Callable[P, RT]:
        func_full_name = func.__qualname__
        CrudRepositoryImplementationService.add_skip_function(func_full_name)
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> RT:
            nonlocal query_template
            return QueryExecutionService.execute_query(query_template, func, kwargs, is_modifying)
        return wrapper
    return decorator
