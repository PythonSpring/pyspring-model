import re
from typing import Dict, Any
from enum import Enum

from pydantic import BaseModel


class ConditionNotation(str,Enum):
    AND = "_and_"
    OR = "_or_"

class FieldOperation(str, Enum):
    """
    Enumeration of supported field operations for dynamic query generation.
    These operations define how a field should be queried in the database.
    """
    EQUALS = "equals"      # Default operation: field = value
    IN = "in"             # field IN (value1, value2, ...)
    GREATER_THAN = "gt"   # field > value
    GREATER_EQUAL = "gte" # field >= value
    LESS_THAN = "lt"      # field < value
    LESS_EQUAL = "lte"    # field <= value
    LIKE = "like"         # field LIKE pattern
    NOT_EQUALS = "ne"     # field != value
    NOT_IN = "not_in"     # field NOT IN (value1, value2, ...)


class _Query(BaseModel):
    """
    A data model representing a query with the following fields:
    - `conditions`: A list of string conditions that will be used to filter the query.
    - `is_one_result`: A boolean indicating whether the query should return a single result or a list of results.
    - `required_fields`: A list of string field names that should be included in the query result.
    - `field_operations`: A dictionary mapping field names to their operations (e.g., "in" for IN operator).
    """

    raw_query_list: list[str]
    is_one_result: bool
    notations: list[ConditionNotation]
    required_fields: list[str]
    field_operations: Dict[str, FieldOperation] = {}


class _MetodQueryBuilder:
    """
    The `MetodQueryBuilder` class is responsible for parsing a method name and extracting the fields and conditions to be used in a database query.
    It takes a method name as input and returns a `Query` object that contains the parsed information.
    The `parse_query()` method is the main entry point for this functionality.
    It analyzes the method name and determines the appropriate pattern to use for extracting the fields and conditions.
    The method name is expected to follow a specific convention, such as `get_by_name_and_age` or `find_all_by_name_or_age`.
    The method then splits the extracted conditions by `_and_` and `_or_` and returns a `Query` object with the parsed information.
    """

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name

    def parse_query(self) -> _Query:
        """
        Parse the method name to extract fields and conditions.
        Example:
            - 'find_by_name_and_age' -> Query(raw_query_list=['name', '_and_', 'age'], is_one_result=True, required_fields=['name', 'age'])
            - 'find_all_by_name_or_age' -> Query(raw_query_list=['name', '_or_', 'age'], is_one_result=False, required_fields=['name', 'age'])
            - 'find_by_status_in' -> Query(raw_query_list=['status'], is_one_result=True, required_fields=['status'], field_operations={'status': FieldOperation.IN})
            - 'find_by_age_gt' -> Query(raw_query_list=['age'], is_one_result=True, required_fields=['age'], field_operations={'age': FieldOperation.GREATER_THAN})
        """
        is_one = False
        pattern = ""   
        if self.method_name.startswith("get_by"):
            pattern = r"get_by_(.*)"
            is_one = True
        elif self.method_name.startswith("find_by"):
            pattern = r"find_by_(.*)"
            is_one = True
        elif self.method_name.startswith("find_all_by"):
            pattern = r"find_all_by_(.*)"
        elif self.method_name.startswith("get_all_by"):
            pattern = r"get_all_by_(.*)"

        if len(pattern) == 0:
            raise ValueError(f"Method name must start with 'get_by', 'find_by', 'find_all_by', or 'get_all_by': {self.method_name}")

        match = re.match(pattern, self.method_name)
        if not match:
            raise ValueError(f"Invalid method name: {self.method_name}")

        raw_query = match.group(1)
        # Split fields by '_and_' or '_or_' and keep logical operators
        raw_query_list = re.split(r"(_and_|_or_)", raw_query)

        # Extract required fields and detect operations
        required_fields = []
        field_operations = {}
        
        for field in raw_query_list:
            if field not in ["_and_", "_or_"]:
                # Check for field operations
                operation = self._detect_field_operation(field)
                if operation:
                    base_field = self._extract_base_field(field, operation)
                    required_fields.append(base_field)
                    field_operations[base_field] = operation
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
        )

    def _detect_field_operation(self, field: str) -> FieldOperation | None:
        """
        Detect field operation based on field suffix.
        
        Args:
            field: The field name with potential operation suffix
            
        Returns:
            FieldOperation if detected, None if no operation suffix found
        """
        # Check for _not_in first (longer suffix) to avoid matching _in
        if field.endswith("_not_in"):
            return FieldOperation.NOT_IN
        
        operation_suffixes = {
            "_in": FieldOperation.IN,
            "_gt": FieldOperation.GREATER_THAN,
            "_gte": FieldOperation.GREATER_EQUAL,
            "_lt": FieldOperation.LESS_THAN,
            "_lte": FieldOperation.LESS_EQUAL,
            "_like": FieldOperation.LIKE,
            "_ne": FieldOperation.NOT_EQUALS,
        }
        
        for suffix, operation in operation_suffixes.items():
            if field.endswith(suffix):
                return operation
        
        return None

    def _extract_base_field(self, field: str, operation: FieldOperation) -> str:
        """
        Extract the base field name by removing the operation suffix.
        
        Args:
            field: The field name with operation suffix
            operation: The detected field operation
            
        Returns:
            The base field name without operation suffix
        """
        operation_suffixes = {
            FieldOperation.IN: "_in",
            FieldOperation.GREATER_THAN: "_gt",
            FieldOperation.GREATER_EQUAL: "_gte",
            FieldOperation.LESS_THAN: "_lt",
            FieldOperation.LESS_EQUAL: "_lte",
            FieldOperation.LIKE: "_like",
            FieldOperation.NOT_EQUALS: "_ne",
            FieldOperation.NOT_IN: "_not_in",
        }
        
        suffix = operation_suffixes[operation]
        return field[:-len(suffix)]
