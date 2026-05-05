"""
Tests for PySpringModelProperties defaults.
"""

from py_spring_model.core.commons import PySpringModelProperties


class TestPySpringModelProperties:
    def test_key_value(self):
        assert PySpringModelProperties.__key__ == "py_spring_model"

    def test_create_all_tables_defaults_to_true(self):
        props = PySpringModelProperties(sqlalchemy_database_uri="sqlite:///:memory:")
        assert props.create_all_tables is True

    def test_create_crud_routes_defaults_to_false(self):
        props = PySpringModelProperties(sqlalchemy_database_uri="sqlite:///:memory:")
        assert props.create_crud_routes is False

    def test_explicit_values_override_defaults(self):
        props = PySpringModelProperties(
            sqlalchemy_database_uri="sqlite:///test.db",
            create_all_tables=False,
            create_crud_routes=True,
        )
        assert props.sqlalchemy_database_uri == "sqlite:///test.db"
        assert props.create_all_tables is False
        assert props.create_crud_routes is True
