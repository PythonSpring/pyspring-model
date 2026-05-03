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
from sqlalchemy import ColumnElement, delete, func
from sqlalchemy.sql import and_, or_
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from py_spring_model.core.model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.repository.crud_repository import CrudRepository
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
    FieldOperation,
    ConditionNotation,
    QueryType,
)

PySpringModelT = TypeVar("PySpringModelT", bound=PySpringModel)


class CrudRepositoryImplementationService:
    """
    The `CrudRepositoryImplementationService` class is responsible for implementing the query logic for the `CrudRepository` inheritors.
    It dynamically generates wrapper methods for the additional methods defined in the `CrudRepository` inheritors.
    """

    skip_functions: ClassVar[set[str]] = set()

    @classmethod
    def add_skip_function(cls, func_name: str) -> None:
        cls.skip_functions.add(func_name)

    def __init__(self) -> None:
        self.basic_crud_methods = dir(CrudRepository)
        self.class_already_implemented: set[str] = set()

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
                or method_name.startswith("count_by")
                or method_name.startswith("exists_by")
                or method_name.startswith("delete_by")
                or method_name.startswith("delete_all_by")
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

            param_to_field_mapping = self._create_parameter_field_mapping(
                list(copy_annotations.keys()), query.required_fields
            )

            if len(copy_annotations) != len(query.required_fields):
                raise ValueError(
                    f"Invalid number of annotations. Expected {query.required_fields}, received {list(copy_annotations.keys())}."
                )

            wrapped_method = self.create_implementation_wrapper(query, model_type, copy_annotations, param_to_field_mapping)
            logger.info(
                f"Binding method: {method} to {repository_type}, with query: {query}"
            )
            setattr(repository_type, method, wrapped_method)

    def _create_parameter_field_mapping(self, param_names: list[str], field_names: list[str]) -> dict[str, str]:
        """
        Create a mapping between parameter names and field names.
        Supports exact matching and common plural-to-singular mapping.
        """
        mapping = {}
        unmatched_params = []

        field_set = set(field_names)

        for param_name in param_names:
            if param_name in field_set:
                mapping[param_name] = param_name
                continue

            if param_name.endswith('s') and len(param_name) > 1:
                singular_candidate = self._cast_plural_to_singular(param_name)
                if singular_candidate in field_set:
                    plural_candidate = singular_candidate + 's'
                    if plural_candidate not in field_set:
                        mapping[param_name] = singular_candidate
                        continue

            unmatched_params.append(param_name)

        if unmatched_params:
            error_msg = "Parameter to field mapping failed:\n"
            error_msg += f"  Unmatched parameters: {unmatched_params}\n"
            error_msg += f"  Available fields: {field_names}\n"
            error_msg += f"  Provided parameters: {param_names}\n"
            error_msg += "  Note: Parameters must exactly match field names or be plural forms (add 's')"
            raise ValueError(error_msg)

        return mapping

    def _cast_plural_to_singular(self, word: str) -> str:
        if word.endswith('ies'):
            return word[:-3] + 'y'
        elif word.endswith('ses'):
            return word[:-2]
        else:
            return word[:-1]

    def create_implementation_wrapper(self, query: _Query, model_type: Type[PySpringModel], original_func_annotations: dict[str, Any], param_to_field_mapping: dict[str, str]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            field_kwargs = {}
            for param_name, value in kwargs.items():
                if param_name in param_to_field_mapping:
                    field_name = param_to_field_mapping[param_name]
                    field_kwargs[field_name] = value
                else:
                    raise ValueError(f"Unknown parameter '{param_name}'. Expected parameters: {list(param_to_field_mapping.keys())}")

            filter_conditions = self._build_filter_conditions(model_type, query, field_kwargs)
            combined_condition = self._combine_conditions_with_notations(filter_conditions, [ConditionNotation(notation) for notation in query.notations])

            match query.query_type:
                case QueryType.COUNT:
                    return self._execute_count(model_type, combined_condition)
                case QueryType.EXISTS:
                    return self._execute_exists(model_type, combined_condition)
                case QueryType.DELETE:
                    return self._execute_delete(model_type, combined_condition)
                case _:
                    sql_statement = select(model_type)
                    if combined_condition is not None:
                        sql_statement = sql_statement.where(combined_condition)
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
        """Build SQL statement from parsed query and parameters."""
        filter_conditions = self._build_filter_conditions(model_type, parsed_query, params)
        combined_condition = self._combine_conditions_with_notations(filter_conditions, [ConditionNotation(notation) for notation in parsed_query.notations])

        query = select(model_type)
        if combined_condition is not None:
            query = query.where(combined_condition)
        return query

    def _build_filter_conditions(
        self,
        model_type: Type[PySpringModelT],
        parsed_query: _Query,
        params: dict[str, Any],
    ) -> list[ColumnElement[bool]]:
        """Build individual filter conditions for each field."""
        filter_conditions = []

        for field in parsed_query.required_fields:
            # BETWEEN fields use min_/max_ prefixes - skip them here, handled below
            if field.startswith("min_") or field.startswith("max_"):
                continue
            column = getattr(model_type, field)
            optional_param_value = params.get(field, None)
            if optional_param_value is None:
                raise ValueError(f"Required field '{field}' is missing or None in keyword arguments. All required fields must be provided with non-None values, getting {params}")
            condition = self._create_field_condition(column, field, optional_param_value, parsed_query.field_operations)
            filter_conditions.append(condition)

        # Handle BETWEEN fields
        for field, operation in parsed_query.field_operations.items():
            if operation == FieldOperation.BETWEEN:
                column = getattr(model_type, field)
                min_key = f"min_{field}"
                max_key = f"max_{field}"
                min_val = params.get(min_key)
                max_val = params.get(max_key)
                if min_val is None or max_val is None:
                    raise ValueError(f"BETWEEN operation for field '{field}' requires both '{min_key}' and '{max_key}' parameters")
                filter_conditions.append(column.between(min_val, max_val))

        # Handle null check fields (IS_NULL, IS_NOT_NULL)
        for field in parsed_query.null_check_fields:
            column = getattr(model_type, field)
            operation = parsed_query.field_operations[field]
            if operation == FieldOperation.IS_NULL:
                filter_conditions.append(column.is_(None))
            elif operation == FieldOperation.IS_NOT_NULL:
                filter_conditions.append(column.isnot(None))

        return filter_conditions

    def _create_field_condition(
        self,
        column: Any,
        field: str,
        param_value: Any,
        field_operations: dict[str, FieldOperation],
    ) -> ColumnElement[bool]:
        """Create a condition for a single field based on its operation type."""
        if field not in field_operations:
            return column == param_value

        operation = field_operations[field]

        match operation:
            case FieldOperation.IN:
                return self._create_in_condition(column, param_value)
            case FieldOperation.GREATER_THAN:
                return column > param_value
            case FieldOperation.GREATER_EQUAL:
                return column >= param_value
            case FieldOperation.LESS_THAN:
                return column < param_value
            case FieldOperation.LESS_EQUAL:
                return column <= param_value
            case FieldOperation.LIKE:
                return column.like(param_value)
            case FieldOperation.NOT_EQUALS:
                return column != param_value
            case FieldOperation.NOT_IN:
                return self._create_not_in_condition(column, param_value)
            case FieldOperation.STARTS_WITH:
                return column.like(f"{param_value}%")
            case FieldOperation.ENDS_WITH:
                return column.like(f"%{param_value}")
            case FieldOperation.CONTAINS:
                return column.like(f"%{param_value}%")
            case FieldOperation.NOT_LIKE:
                return ~column.like(param_value)
            case _:
                return column == param_value

    def _create_in_condition(self, column: Any, param_value: Any) -> ColumnElement[bool]:
        """Create an IN condition with proper validation and edge case handling."""
        if not isinstance(param_value, (list, tuple, set)):
            raise ValueError(
                f"Parameter for IN operation must be a collection (list, tuple, or set), got {type(param_value)}"
            )

        if len(param_value) == 0:
            return column == None

        return column.in_(param_value)

    def _create_not_in_condition(self, column: Any, param_value: Any) -> ColumnElement[bool]:
        """Create a NOT IN condition with proper validation and edge case handling."""
        if not isinstance(param_value, (list, tuple, set)):
            raise ValueError(
                f"Parameter for NOT IN operation must be a collection (list, tuple, or set), got {type(param_value)}"
            )

        if len(param_value) == 0:
            return column != None

        return ~column.in_(param_value)

    def _combine_conditions_with_notations(
        self,
        filter_conditions: list[ColumnElement[bool]],
        notations: list[ConditionNotation],
    ) -> ColumnElement[bool] | None:
        """Combine filter conditions using logical operators (AND/OR)."""
        if not filter_conditions:
            return None

        condition_stack = filter_conditions.copy()

        for notation in notations:
            if len(condition_stack) >= 2:
                right_condition = condition_stack.pop(0)
                left_condition = condition_stack.pop(0)
                combined = self._apply_logical_operator(left_condition, right_condition, notation)
                condition_stack.append(combined)

        return condition_stack[0] if condition_stack else None

    def _apply_logical_operator(
        self,
        left_condition: ColumnElement[bool],
        right_condition: ColumnElement[bool],
        notation: ConditionNotation,
    ) -> ColumnElement[bool]:
        """Apply logical operator (AND/OR) to two conditions."""
        match notation:
            case ConditionNotation.AND:
                return and_(left_condition, right_condition)
            case ConditionNotation.OR:
                return or_(left_condition, right_condition)

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

    @Transactional
    def _execute_count(self, model_type: Type[PySpringModelT], condition) -> int:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(model_type)
        if condition is not None:
            statement = statement.where(condition)
        return session.exec(statement).one()

    @Transactional
    def _execute_exists(self, model_type: Type[PySpringModelT], condition) -> bool:
        session = SessionContextHolder.get_or_create_session()
        statement = select(func.count()).select_from(model_type)
        if condition is not None:
            statement = statement.where(condition)
        return session.exec(statement).one() > 0

    @Transactional
    def _execute_delete(self, model_type: Type[PySpringModelT], condition) -> int:
        session = SessionContextHolder.get_or_create_session()
        statement = delete(model_type)
        if condition is not None:
            statement = statement.where(condition)
        result = session.execute(statement)
        return result.rowcount

    def implement_query_for_all_crud_repository_inheritors(self) -> None:
        for crud_repository_cls in self.get_all_crud_repository_inheritors():
            if crud_repository_cls.__name__ in self.class_already_implemented:
                continue
            self._implemenmt_query(crud_repository_cls)
            self.class_already_implemented.add(crud_repository_cls.__name__)

P = ParamSpec("P")
T = TypeVar("T", bound=BaseModel)
RT = TypeVar("RT", bound=Union[T, None, list[T]])  # type: ignore


def SkipAutoImplmentation(func: Callable[P, RT]) -> Callable[P, RT]:
    """
    Decorator to skip the auto implementation for a method.
    """
    func_name = func.__qualname__
    logger.info(f"Skipping auto implementation for function: {func_name}")
    CrudRepositoryImplementationService.add_skip_function(func_name)
    return func
