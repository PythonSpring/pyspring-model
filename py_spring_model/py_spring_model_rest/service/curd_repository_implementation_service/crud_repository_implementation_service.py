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
    FieldOperation,
    ConditionNotation
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

            # Create parameter to field mapping for better API design
            param_to_field_mapping = self._create_parameter_field_mapping(
                list(copy_annotations.keys()), query.required_fields
            )

            if len(copy_annotations) != len(query.required_fields):
                raise ValueError(
                    f"Invalid number of annotations. Expected {query.required_fields}, received {list(copy_annotations.keys())}."
                )
            
            # Create a wrapper for the current method and query
            wrapped_method = self.create_implementation_wrapper(query, model_type, copy_annotations, param_to_field_mapping)
            logger.info(
                f"Binding method: {method} to {repository_type}, with query: {query}"
            )
            setattr(repository_type, method, wrapped_method)

    def _create_parameter_field_mapping(self, param_names: list[str], field_names: list[str]) -> dict[str, str]:
        """
        Create a mapping between parameter names and field names.
        
        Supports exact matching and common plural-to-singular mapping:
        - Exact match: 'name' -> 'name'
        - Plural to singular: 'names' -> 'name', 'ages' -> 'age'
        
        Rules:
        1. Parameter names must match field names exactly, OR
        2. Parameter names can be plural forms of field names (add 's')
        3. No ambiguity allowed (e.g., can't have both 'name' and 'names' as fields)
        
        Examples:
        - param_names: ['name', 'age'], field_names: ['name', 'age'] -> {'name': 'name', 'age': 'age'}
        - param_names: ['names', 'ages'], field_names: ['name', 'age'] -> {'names': 'name', 'ages': 'age'}
        - param_names: ['name', 'ages'], field_names: ['name', 'age'] -> {'name': 'name', 'ages': 'age'}
        """
        mapping = {}
        unmatched_params = []
        
        # Create a set of field names for efficient lookup
        field_set = set(field_names)
        
        for param_name in param_names:
            # Try exact match first
            if param_name in field_set:
                mapping[param_name] = param_name
                continue
            
            # Try plural-to-singular mapping (only if param ends with 's' and is longer than 1 char)
            if param_name.endswith('s') and len(param_name) > 1:
                # Handle special cases for words ending with 's'
                if param_name.endswith('ies'):
                    # words ending with 'ies' -> 'y' (e.g., 'categories' -> 'category')
                    singular_candidate = param_name[:-3] + 'y'
                elif param_name.endswith('ses'):
                    # words ending with 'ses' -> 's' (e.g., 'statuses' -> 'status')
                    singular_candidate = param_name[:-2]
                else:
                    # regular plural: remove 's'
                    singular_candidate = param_name[:-1]
                
                if singular_candidate in field_set:
                    # Check for ambiguity: make sure we don't have both singular and plural forms as fields
                    plural_candidate = singular_candidate + 's'
                    if plural_candidate not in field_set:
                        mapping[param_name] = singular_candidate
                        continue
            
            # No match found
            unmatched_params.append(param_name)
        
        # Check if all parameters were mapped
        if unmatched_params:
            error_msg = "Parameter to field mapping failed:\n"
            error_msg += f"  Unmatched parameters: {unmatched_params}\n"
            error_msg += f"  Available fields: {field_names}\n"
            error_msg += f"  Provided parameters: {param_names}\n"
            error_msg += "  Note: Parameters must exactly match field names or be plural forms (add 's')"
            raise ValueError(error_msg)
        
        return mapping

    def create_implementation_wrapper(self, query: _Query, model_type: Type[PySpringModel], original_func_annotations: dict[str, Any], param_to_field_mapping: dict[str, str]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            if len(query.required_fields) > 0:
                # Simple mapping: parameter names must match field names exactly
                field_kwargs = {}
                for param_name, value in kwargs.items():
                    if param_name in param_to_field_mapping:
                        field_name = param_to_field_mapping[param_name]
                        field_kwargs[field_name] = value
                    else:
                        raise ValueError(f"Unknown parameter '{param_name}'. Expected parameters: {list(param_to_field_mapping.keys())}")

                # Execute the query
                sql_statement = self._get_sql_statement(model_type, query, field_kwargs)
                result = self._session_execute(sql_statement, query.is_one_result)
                logger.info(f"Executing query with params: {kwargs}")
                return result
            else:
                # No required fields, execute without parameters
                sql_statement = self._get_sql_statement(model_type, query, {})
                result = self._session_execute(sql_statement, query.is_one_result)
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
            column = getattr(model_type, field)
            param_value = params[field]
            condition = self._create_field_condition(column, field, param_value, parsed_query.field_operations)
            filter_conditions.append(condition)
        
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
            case _:
                # Default to equality for unknown operations
                return column == param_value

    def _create_in_condition(self, column: Any, param_value: Any) -> ColumnElement[bool]:
        """Create an IN condition with proper validation and edge case handling."""
        if not isinstance(param_value, (list, tuple, set)):
            raise ValueError(
                f"Parameter for IN operation must be a collection (list, tuple, or set), got {type(param_value)}"
            )
        
        # Handle empty list case - return a condition that's always false
        if len(param_value) == 0:
            return column == None
        
        return column.in_(param_value)

    def _create_not_in_condition(self, column: Any, param_value: Any) -> ColumnElement[bool]:
        """Create a NOT IN condition with proper validation and edge case handling."""
        if not isinstance(param_value, (list, tuple, set)):
            raise ValueError(
                f"Parameter for NOT IN operation must be a collection (list, tuple, or set), got {type(param_value)}"
            )
        
        # Handle empty list case - return a condition that's always true
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
        
        # Use stack-based approach to maintain original order
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