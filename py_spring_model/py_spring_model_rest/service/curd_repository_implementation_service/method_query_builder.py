import re
from typing import Dict, Any

from pydantic import BaseModel


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
    notations: list[str]
    required_fields: list[str]
    field_operations: Dict[str, str] = {}


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
            - 'find_by_status_in' -> Query(raw_query_list=['status'], is_one_result=True, required_fields=['status'], field_operations={'status': 'in'})
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
                # Check for IN operation
                if field.endswith("_in"):
                    base_field = field[:-3]  # Remove "_in" suffix
                    required_fields.append(base_field)
                    field_operations[base_field] = "in"
                else:
                    required_fields.append(field)

        return _Query(
            raw_query_list=raw_query_list,
            is_one_result=is_one,
            required_fields=required_fields,
            notations=[
                notation for notation in raw_query_list if notation in ["_and_", "_or_"]
            ],
            field_operations=field_operations,
        )
