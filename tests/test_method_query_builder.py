import pytest

from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import _MetodQueryBuilder, _Query


class TestMetodQueryBuilder:
    @pytest.mark.parametrize(
        "method_name, expected_raw_query_list, expected_is_one_result, expected_required_fields, expected_notations, expected_field_operations",
        [
            (
                "get_by_name_and_age",
                ["name", "_and_", "age"],
                True,
                ["name", "age"],
                ["_and_"],
                {},
            ),
            (
                "find_by_name_or_age",
                ["name", "_or_", "age"],
                True,
                ["name", "age"],
                ["_or_"],
                {},
            ),
            (
                "find_all_by_name_and_age",
                ["name", "_and_", "age"],
                False,
                ["name", "age"],
                ["_and_"],
                {},
            ),
            (
                "get_all_by_city_or_country",
                ["city", "_or_", "country"],
                False,
                ["city", "country"],
                ["_or_"],
                {},
            ),
            (
                "find_by_status_in",
                ["status_in"],
                True,
                ["status"],
                [],
                {"status": "in"},
            ),
            (
                "find_all_by_id_in",
                ["id_in"],
                False,
                ["id"],
                [],
                {"id": "in"},
            ),
            (
                "find_by_status_in_and_name",
                ["status_in", "_and_", "name"],
                True,
                ["status", "name"],
                ["_and_"],
                {"status": "in"},
            ),
            (
                "find_by_status_in_or_category_in",
                ["status_in", "_or_", "category_in"],
                True,
                ["status", "category"],
                ["_or_"],
                {"status": "in", "category": "in"},
            ),
        ],
    )
    def test_parse_query(
        self,
        method_name,
        expected_raw_query_list,
        expected_is_one_result,
        expected_required_fields,
        expected_notations,
        expected_field_operations,
    ):
        builder = _MetodQueryBuilder(method_name)
        query = builder.parse_query()

        assert isinstance(query, _Query)
        assert query.raw_query_list == expected_raw_query_list
        assert query.is_one_result == expected_is_one_result
        assert query.required_fields == expected_required_fields
        assert query.notations == expected_notations
        assert query.field_operations == expected_field_operations

    def test_invalid_method_name(self):
        invalid_method_name = "invalid_method_name"
        with pytest.raises(ValueError) as excinfo:
            builder = _MetodQueryBuilder(invalid_method_name)
            builder.parse_query()

        assert "Method name must start with 'get_by', 'find_by', 'find_all_by', or 'get_all_by" in str(excinfo.value)

    def test_empty_method_name(self):
        with pytest.raises(ValueError) as excinfo:
            builder = _MetodQueryBuilder("")
            builder.parse_query()

        assert "Method name must start with 'get_by', 'find_by', 'find_all_by', or 'get_all_by" in str(excinfo.value)