import re
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel
from sqlalchemy.exc import NoInspectionAvailable


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


class _FieldReference(BaseModel):
    """Represents a field that may traverse a relationship."""

    field_name: str
    relationship_name: Optional[str] = None
    related_model: Optional[Any] = None  # Type[PySpringModel], Any to avoid circular import


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
    field_references: Dict[str, _FieldReference] = {}


def get_relationship_fields(model_type: type) -> dict[str, type]:
    """
    Introspect a SQLModel class to find all Relationship fields.
    Returns a dict mapping relationship_name -> target model class.

    Uses SQLAlchemy's inspect() to read the resolved relationship properties,
    which handles forward references that have been resolved at class init time.
    """
    from sqlalchemy import inspect as sa_inspect

    relationships: dict[str, type] = {}

    try:
        mapper = sa_inspect(model_type)
    except NoInspectionAvailable:
        return relationships

    for rel in mapper.relationships:
        target_cls = rel.mapper.class_
        relationships[rel.key] = target_cls

    return relationships


def _get_column_names(model_type: type) -> set[str]:
    """Return the set of direct column attribute names for a SQLModel class."""
    from sqlalchemy import inspect as sa_inspect

    try:
        mapper = sa_inspect(model_type)
    except NoInspectionAvailable:
        return set()
    return {col.key for col in mapper.columns}


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
    _OPERATION_TO_SUFFIX: dict[FieldOperation, str] = {
        v: k for k, v in _OPERATION_SUFFIXES.items()
    }

    # (prefix, regex_pattern, is_one_result, query_type)
    # Order matters: longer prefixes must come before shorter ones (e.g. delete_all_by before delete_by).
    _PREFIX_RULES: list[tuple[str, str, bool, QueryType]] = [
        ("count_by", r"count_by_(.*)", True, QueryType.COUNT),
        ("exists_by", r"exists_by_(.*)", True, QueryType.EXISTS),
        ("delete_all_by", r"delete_all_by_(.*)", False, QueryType.DELETE),
        ("delete_by", r"delete_by_(.*)", True, QueryType.DELETE),
        ("get_by", r"get_by_(.*)", True, QueryType.SELECT_ONE),
        ("find_by", r"find_by_(.*)", True, QueryType.SELECT_ONE),
        ("find_all_by", r"find_all_by_(.*)", False, QueryType.SELECT_MANY),
        ("get_all_by", r"get_all_by_(.*)", False, QueryType.SELECT_MANY),
    ]

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name

    def _match_prefix(self) -> tuple[str, bool, QueryType]:
        for prefix, pattern, is_one, query_type in self._PREFIX_RULES:
            if self.method_name.startswith(prefix):
                return pattern, is_one, query_type

        valid = ", ".join(f"'{p}'" for p, *_ in self._PREFIX_RULES)
        raise ValueError(f"Method name must start with {valid}: {self.method_name}")

    def parse_query(self, model_type: type | None = None) -> _Query:
        """Parse a method name into a structured _Query.

        Args:
            model_type: Optional model class for relationship introspection.
                         When provided, field tokens are checked against the model's
                         Relationship fields to detect join traversals.

        Algorithm:
          1. Match the method name against _PREFIX_RULES to determine the regex
             pattern, whether the query returns a single result, and the QueryType
             (SELECT_ONE, SELECT_MANY, COUNT, EXISTS, DELETE).
          2. Extract the portion after the prefix (e.g. "name_and_age_gt" from
             "find_by_name_and_age_gt") and split on _and_ / _or_ to get raw tokens.
          3. Resolve relationships if model_type is provided.
          4. For each token (skipping _and_ / _or_ connectors):
             - Strip any operation suffix to get the base token.
             - Try to resolve as a relationship traversal (e.g. "children_status").
             - If relationship match found, record a _FieldReference.
             - Otherwise, treat as a direct column (existing behavior).
          5. Return a _Query combining the raw tokens, required fields, notations,
             field operations, query type, null-check fields, and field references.
        """
        pattern, is_one, query_type = self._match_prefix()

        match = re.match(pattern, self.method_name)
        if not match:
            raise ValueError(f"Invalid method name: {self.method_name}")

        raw_query = match.group(1)
        raw_query_list = re.split(r"(_and_|_or_)", raw_query)

        # Resolve relationships and direct columns if model_type is provided
        rel_fields: dict[str, type] = {}
        direct_columns: set[str] = set()
        if model_type is not None:
            rel_fields = get_relationship_fields(model_type)
            direct_columns = _get_column_names(model_type)

        required_fields: list[str] = []
        field_operations: Dict[str, FieldOperation] = {}
        null_check_fields: list[str] = []
        field_references: Dict[str, _FieldReference] = {}

        for field in raw_query_list:
            if field in ("_and_", "_or_"):
                continue

            # Strip operation suffix to get base token
            operation = self._detect_field_operation(field)
            base_token = self._extract_base_field(field, operation) if operation else field

            # Resolve the field name: relationship traversal or direct column.
            # Direct columns take precedence over relationship traversals for backwards compatibility.
            rel_name, target_field = self._resolve_relationship_token(base_token, rel_fields)
            if rel_name is not None and target_field is not None and base_token not in direct_columns:
                resolved_field = target_field
                field_references[resolved_field] = _FieldReference(
                    field_name=resolved_field,
                    relationship_name=rel_name,
                    related_model=rel_fields[rel_name],
                )
            else:
                resolved_field = base_token

            # Record operation and classify the field
            if operation:
                field_operations[resolved_field] = operation

            if operation == FieldOperation.BETWEEN:
                required_fields.extend([f"min_{resolved_field}", f"max_{resolved_field}"])
            elif operation in (FieldOperation.IS_NULL, FieldOperation.IS_NOT_NULL):
                null_check_fields.append(resolved_field)
            else:
                required_fields.append(resolved_field)

        if model_type is not None and direct_columns:
            self._validate_fields(
                model_type,
                direct_columns,
                required_fields,
                null_check_fields,
                field_operations,
                field_references,
            )

        return _Query(
            raw_query_list=raw_query_list,
            is_one_result=is_one,
            required_fields=required_fields,
            notations=[
                ConditionNotation(notation)
                for notation in raw_query_list
                if notation in ("_and_", "_or_")
            ],
            field_operations=field_operations,
            query_type=query_type,
            null_check_fields=null_check_fields,
            field_references=field_references,
        )

    def _resolve_relationship_token(
        self, base_token: str, rel_fields: dict[str, type]
    ) -> tuple[str | None, str | None]:
        """Check if a base token (with operation suffix already stripped) is a relationship traversal.

        Returns (relationship_name, target_field) if matched, or (None, None) if not.

        Resolution rules:
        1. Sort relationship names by length descending (longest match first)
        2. Check if base_token starts with {rel_name}_
        3. The remainder after {rel_name}_ is the target field on the related model
        4. If no relationship matches, return (None, None) -> treat as direct column
        """
        if not rel_fields:
            return None, None

        # Sort by length descending for longest-prefix-first matching
        sorted_rels = sorted(rel_fields.keys(), key=len, reverse=True)

        for rel_name in sorted_rels:
            prefix = f"{rel_name}_"
            if base_token.startswith(prefix):
                target_field = base_token[len(prefix):]
                if target_field:  # Must have something after the prefix
                    return rel_name, target_field

        return None, None

    def _detect_field_operation(self, field: str) -> FieldOperation | None:
        for suffix, operation in self._OPERATION_SUFFIXES.items():
            if field.endswith(suffix):
                return operation
        return None

    def _extract_base_field(self, field: str, operation: FieldOperation) -> str:
        suffix = self._OPERATION_TO_SUFFIX[operation]
        return field[: -len(suffix)]

    def _validate_fields(
        self,
        model_type: type,
        direct_columns: set[str],
        required_fields: list[str],
        null_check_fields: list[str],
        field_operations: Dict[str, FieldOperation],
        field_references: Dict[str, _FieldReference],
    ) -> None:
        for field in required_fields:
            if field.startswith("min_") or field.startswith("max_"):
                base = field[4:]
                if base not in field_references and base not in direct_columns:
                    raise ValueError(
                        f"Method '{self.method_name}': field '{base}' does not exist on model "
                        f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                    )
                continue
            if field not in field_references and field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )

        for field in null_check_fields:
            if field not in field_references and field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )
