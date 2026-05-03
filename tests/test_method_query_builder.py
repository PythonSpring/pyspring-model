import pytest

from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import _MetodQueryBuilder, _Query, FieldOperation, QueryType


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
                {"status": FieldOperation.IN},
            ),
            (
                "find_all_by_id_in",
                ["id_in"],
                False,
                ["id"],
                [],
                {"id": FieldOperation.IN},
            ),
            (
                "find_by_status_in_and_name",
                ["status_in", "_and_", "name"],
                True,
                ["status", "name"],
                ["_and_"],
                {"status": FieldOperation.IN},
            ),
            (
                "find_by_status_in_or_category_in",
                ["status_in", "_or_", "category_in"],
                True,
                ["status", "category"],
                ["_or_"],
                {"status": FieldOperation.IN, "category": FieldOperation.IN},
            ),
            (
                "find_by_age_gt",
                ["age_gt"],
                True,
                ["age"],
                [],
                {"age": FieldOperation.GREATER_THAN},
            ),
            (
                "find_all_by_price_gte",
                ["price_gte"],
                False,
                ["price"],
                [],
                {"price": FieldOperation.GREATER_EQUAL},
            ),
            (
                "find_by_name_like",
                ["name_like"],
                True,
                ["name"],
                [],
                {"name": FieldOperation.LIKE},
            ),
            (
                "find_by_status_ne",
                ["status_ne"],
                True,
                ["status"],
                [],
                {"status": FieldOperation.NOT_EQUALS},
            ),
            (
                "find_by_age_gt_and_status_in",
                ["age_gt", "_and_", "status_in"],
                True,
                ["age", "status"],
                ["_and_"],
                {"age": FieldOperation.GREATER_THAN, "status": FieldOperation.IN},
            ),
            # New prefixes
            (
                "count_by_status",
                ["status"],
                True,
                ["status"],
                [],
                {},
            ),
            (
                "count_by_name_and_age",
                ["name", "_and_", "age"],
                True,
                ["name", "age"],
                ["_and_"],
                {},
            ),
            (
                "exists_by_email",
                ["email"],
                True,
                ["email"],
                [],
                {},
            ),
            (
                "delete_by_status",
                ["status"],
                True,
                ["status"],
                [],
                {},
            ),
            (
                "delete_all_by_status_and_category",
                ["status", "_and_", "category"],
                False,
                ["status", "category"],
                ["_and_"],
                {},
            ),
            # New field operations
            (
                "find_all_by_age_between",
                ["age_between"],
                False,
                ["min_age", "max_age"],
                [],
                {"age": FieldOperation.BETWEEN},
            ),
            (
                "find_all_by_name_is_null",
                ["name_is_null"],
                False,
                [],
                [],
                {"name": FieldOperation.IS_NULL},
            ),
            (
                "find_all_by_name_is_not_null",
                ["name_is_not_null"],
                False,
                [],
                [],
                {"name": FieldOperation.IS_NOT_NULL},
            ),
            (
                "find_all_by_name_starts_with",
                ["name_starts_with"],
                False,
                ["name"],
                [],
                {"name": FieldOperation.STARTS_WITH},
            ),
            (
                "find_all_by_name_ends_with",
                ["name_ends_with"],
                False,
                ["name"],
                [],
                {"name": FieldOperation.ENDS_WITH},
            ),
            (
                "find_all_by_name_contains",
                ["name_contains"],
                False,
                ["name"],
                [],
                {"name": FieldOperation.CONTAINS},
            ),
            (
                "find_all_by_name_not_like",
                ["name_not_like"],
                False,
                ["name"],
                [],
                {"name": FieldOperation.NOT_LIKE},
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

        assert "Method name must start with" in str(excinfo.value)

    def test_empty_method_name(self):
        with pytest.raises(ValueError) as excinfo:
            builder = _MetodQueryBuilder("")
            builder.parse_query()

        assert "Method name must start with" in str(excinfo.value)

    # QueryType tests
    def test_query_type_count_by(self):
        query = _MetodQueryBuilder("count_by_status").parse_query()
        assert query.query_type == QueryType.COUNT

    def test_query_type_exists_by(self):
        query = _MetodQueryBuilder("exists_by_email").parse_query()
        assert query.query_type == QueryType.EXISTS

    def test_query_type_delete_by(self):
        query = _MetodQueryBuilder("delete_by_status").parse_query()
        assert query.query_type == QueryType.DELETE

    def test_query_type_delete_all_by(self):
        query = _MetodQueryBuilder("delete_all_by_status").parse_query()
        assert query.query_type == QueryType.DELETE

    def test_query_type_find_by(self):
        query = _MetodQueryBuilder("find_by_name").parse_query()
        assert query.query_type == QueryType.SELECT_ONE

    def test_query_type_find_all_by(self):
        query = _MetodQueryBuilder("find_all_by_name").parse_query()
        assert query.query_type == QueryType.SELECT_MANY

    # Null check fields tests
    def test_null_check_fields_is_null(self):
        query = _MetodQueryBuilder("find_all_by_name_is_null").parse_query()
        assert "name" in query.null_check_fields
        assert "name" not in query.required_fields

    def test_null_check_fields_is_not_null(self):
        query = _MetodQueryBuilder("find_all_by_name_is_not_null").parse_query()
        assert "name" in query.null_check_fields
        assert "name" not in query.required_fields

    def test_between_fields(self):
        query = _MetodQueryBuilder("find_all_by_age_between").parse_query()
        assert "min_age" in query.required_fields
        assert "max_age" in query.required_fields
        assert "age" not in query.required_fields
