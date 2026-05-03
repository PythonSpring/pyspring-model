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

    # Suffix -> FieldOperation mapping. Order matters: longer suffixes first to avoid partial matches.
    _OPERATION_SUFFIXES: dict[str, FieldOperation] = {
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

    # Reverse lookup: FieldOperation -> suffix string.
    _OPERATION_TO_SUFFIX: dict[FieldOperation, str] = {v: k for k, v in _OPERATION_SUFFIXES.items()}

    # (prefix, regex_pattern, is_one_result, query_type)
    # Order matters: longer prefixes must come before shorter ones (e.g. delete_all_by before delete_by).
    _PREFIX_RULES: list[tuple[str, str, bool, QueryType]] = [
        ("count_by",      r"count_by_(.*)",      True,  QueryType.COUNT),
        ("exists_by",     r"exists_by_(.*)",     True,  QueryType.EXISTS),
        ("delete_all_by", r"delete_all_by_(.*)", False, QueryType.DELETE),
        ("delete_by",     r"delete_by_(.*)",     True,  QueryType.DELETE),
        ("get_by",        r"get_by_(.*)",        True,  QueryType.SELECT_ONE),
        ("find_by",       r"find_by_(.*)",       True,  QueryType.SELECT_ONE),
        ("find_all_by",   r"find_all_by_(.*)",   False, QueryType.SELECT_MANY),
        ("get_all_by",    r"get_all_by_(.*)",    False, QueryType.SELECT_MANY),
    ]

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name

    def _match_prefix(self) -> tuple[str, bool, QueryType]:
        for prefix, pattern, is_one, query_type in self._PREFIX_RULES:
            if self.method_name.startswith(prefix):
                return pattern, is_one, query_type

        valid = ", ".join(f"'{p}'" for p, *_ in self._PREFIX_RULES)
        raise ValueError(
            f"Method name must start with {valid}: {self.method_name}"
        )

    def parse_query(self) -> _Query:
        """Parse a method name into a structured _Query.

        Algorithm:
          1. Match the method name against _PREFIX_RULES to determine the regex
             pattern, whether the query returns a single result, and the QueryType
             (SELECT_ONE, SELECT_MANY, COUNT, EXISTS, DELETE).
          2. Extract the portion after the prefix (e.g. "name_and_age_gt" from
             "find_by_name_and_age_gt") and split on _and_ / _or_ to get raw tokens.
          3. For each token (skipping _and_ / _or_ connectors):
             - Detect a field operation suffix (e.g. _gt, _between, _is_null) via
               _OPERATION_SUFFIXES. If none found, treat the token as a plain field.
             - BETWEEN: adds min_<field> and max_<field> to required_fields.
             - IS_NULL / IS_NOT_NULL: adds field to null_check_fields (no parameter needed).
             - All other operations: adds the base field name to required_fields.
          4. Return a _Query combining the raw tokens, required fields, notations
             (AND/OR connectors), field operations, query type, and null-check fields.
        """
        pattern, is_one, query_type = self._match_prefix()

        match = re.match(pattern, self.method_name)
        if not match:
            raise ValueError(f"Invalid method name: {self.method_name}")

        raw_query = match.group(1)
        raw_query_list = re.split(r"(_and_|_or_)", raw_query)

        required_fields: list[str] = []
        field_operations: Dict[str, FieldOperation] = {}
        null_check_fields: list[str] = []

        for field in raw_query_list:
            if field in ("_and_", "_or_"):
                continue
            operation = self._detect_field_operation(field)
            if not operation:
                required_fields.append(field)
                continue
            base_field = self._extract_base_field(field, operation)
            field_operations[base_field] = operation
            if operation == FieldOperation.BETWEEN:
                required_fields.append(f"min_{base_field}")
                required_fields.append(f"max_{base_field}")
            elif operation in (FieldOperation.IS_NULL, FieldOperation.IS_NOT_NULL):
                null_check_fields.append(base_field)
            else:
                required_fields.append(base_field)

        return _Query(
            raw_query_list=raw_query_list,
            is_one_result=is_one,
            required_fields=required_fields,
            notations=[
                ConditionNotation(notation) for notation in raw_query_list if notation in ("_and_", "_or_")
            ],
            field_operations=field_operations,
            query_type=query_type,
            null_check_fields=null_check_fields,
        )

    def _detect_field_operation(self, field: str) -> FieldOperation | None:
        for suffix, operation in self._OPERATION_SUFFIXES.items():
            if field.endswith(suffix):
                return operation
        return None

    def _extract_base_field(self, field: str, operation: FieldOperation) -> str:
        suffix = self._OPERATION_TO_SUFFIX[operation]
        return field[:-len(suffix)]
