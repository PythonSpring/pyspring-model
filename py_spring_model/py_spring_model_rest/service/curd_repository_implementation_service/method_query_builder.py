import re
from typing import Dict
from enum import Enum

from pydantic import BaseModel


class ConditionNotation(str, Enum):
    AND = "_and_"
    OR = "_or_"


class QueryType(str, Enum):
    SELECT_ONE = "select_one"
    SELECT_MANY = "select_many"
    COUNT = "count"
    EXISTS = "exists"
    DELETE = "delete"


class FieldOperation(str, Enum):
    """
    Enumeration of supported field operations for dynamic query generation.
    These operations define how a field should be queried in the database.
    """
    EQUALS = "equals"
    IN = "in"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    LIKE = "like"
    NOT_EQUALS = "ne"
    NOT_IN = "not_in"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    CONTAINS = "contains"
    NOT_LIKE = "not_like"


class _Query(BaseModel):
    """
    A data model representing a parsed query with fields, conditions, and operations.
    """
    raw_query_list: list[str]
    is_one_result: bool
    notations: list[ConditionNotation]
    required_fields: list[str]
    field_operations: Dict[str, FieldOperation] = {}
    query_type: QueryType = QueryType.SELECT_ONE
    null_check_fields: list[str] = []


class _MetodQueryBuilder:
    """
    Parses a method name and extracts fields, conditions, and query type for dynamic query generation.
    """

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name

    def parse_query(self) -> _Query:
        is_one = False
        pattern = ""
        query_type = QueryType.SELECT_MANY

        if self.method_name.startswith("count_by"):
            pattern = r"count_by_(.*)"
            is_one = True
            query_type = QueryType.COUNT
        elif self.method_name.startswith("exists_by"):
            pattern = r"exists_by_(.*)"
            is_one = True
            query_type = QueryType.EXISTS
        elif self.method_name.startswith("delete_all_by"):
            pattern = r"delete_all_by_(.*)"
            query_type = QueryType.DELETE
        elif self.method_name.startswith("delete_by"):
            pattern = r"delete_by_(.*)"
            is_one = True
            query_type = QueryType.DELETE
        elif self.method_name.startswith("get_by"):
            pattern = r"get_by_(.*)"
            is_one = True
            query_type = QueryType.SELECT_ONE
        elif self.method_name.startswith("find_by"):
            pattern = r"find_by_(.*)"
            is_one = True
            query_type = QueryType.SELECT_ONE
        elif self.method_name.startswith("find_all_by"):
            pattern = r"find_all_by_(.*)"
            query_type = QueryType.SELECT_MANY
        elif self.method_name.startswith("get_all_by"):
            pattern = r"get_all_by_(.*)"
            query_type = QueryType.SELECT_MANY

        if len(pattern) == 0:
            raise ValueError(
                f"Method name must start with 'get_by', 'find_by', 'find_all_by', 'get_all_by', "
                f"'count_by', 'exists_by', 'delete_by', or 'delete_all_by': {self.method_name}"
            )

        match = re.match(pattern, self.method_name)
        if not match:
            raise ValueError(f"Invalid method name: {self.method_name}")

        raw_query = match.group(1)
        raw_query_list = re.split(r"(_and_|_or_)", raw_query)

        required_fields = []
        field_operations = {}
        null_check_fields = []

        for field in raw_query_list:
            if field not in ["_and_", "_or_"]:
                operation = self._detect_field_operation(field)
                if operation:
                    base_field = self._extract_base_field(field, operation)
                    field_operations[base_field] = operation
                    if operation == FieldOperation.BETWEEN:
                        required_fields.append(f"min_{base_field}")
                        required_fields.append(f"max_{base_field}")
                    elif operation in (FieldOperation.IS_NULL, FieldOperation.IS_NOT_NULL):
                        null_check_fields.append(base_field)
                    else:
                        required_fields.append(base_field)
                else:
                    required_fields.append(field)

        return _Query(
            raw_query_list=raw_query_list,
            is_one_result=is_one,
            required_fields=required_fields,
            notations=[
                ConditionNotation(notation) for notation in raw_query_list if notation in ["_and_", "_or_"]
            ],
            field_operations=field_operations,
            query_type=query_type,
            null_check_fields=null_check_fields,
        )

    def _detect_field_operation(self, field: str) -> FieldOperation | None:
        """Detect field operation based on field suffix. Order matters - longer suffixes first."""
        operation_suffixes = {
            "_is_not_null": FieldOperation.IS_NOT_NULL,
            "_is_null": FieldOperation.IS_NULL,
            "_not_like": FieldOperation.NOT_LIKE,
            "_not_in": FieldOperation.NOT_IN,
            "_starts_with": FieldOperation.STARTS_WITH,
            "_ends_with": FieldOperation.ENDS_WITH,
            "_contains": FieldOperation.CONTAINS,
            "_between": FieldOperation.BETWEEN,
            "_in": FieldOperation.IN,
            "_gte": FieldOperation.GREATER_EQUAL,
            "_gt": FieldOperation.GREATER_THAN,
            "_lte": FieldOperation.LESS_EQUAL,
            "_lt": FieldOperation.LESS_THAN,
            "_like": FieldOperation.LIKE,
            "_ne": FieldOperation.NOT_EQUALS,
        }

        for suffix, operation in operation_suffixes.items():
            if field.endswith(suffix):
                return operation

        return None

    def _extract_base_field(self, field: str, operation: FieldOperation) -> str:
        """Extract the base field name by removing the operation suffix."""
        operation_suffixes = {
            FieldOperation.IN: "_in",
            FieldOperation.GREATER_THAN: "_gt",
            FieldOperation.GREATER_EQUAL: "_gte",
            FieldOperation.LESS_THAN: "_lt",
            FieldOperation.LESS_EQUAL: "_lte",
            FieldOperation.LIKE: "_like",
            FieldOperation.NOT_EQUALS: "_ne",
            FieldOperation.NOT_IN: "_not_in",
            FieldOperation.BETWEEN: "_between",
            FieldOperation.IS_NULL: "_is_null",
            FieldOperation.IS_NOT_NULL: "_is_not_null",
            FieldOperation.STARTS_WITH: "_starts_with",
            FieldOperation.ENDS_WITH: "_ends_with",
            FieldOperation.CONTAINS: "_contains",
            FieldOperation.NOT_LIKE: "_not_like",
        }

        suffix = operation_suffixes[operation]
        return field[:-len(suffix)]
