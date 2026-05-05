"""
Tests for QueryExecutionService return type handling.
Covers: None return type, scalar types (float/str/bool), Optional scalar,
no-result error, invalid return type, missing annotation.
"""

from typing import List, Optional

import pytest
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.query_service.query import (
    Query,
    QueryExecutionService,
)
from py_spring_model.repository.crud_repository import CrudRepository


class ReturnTypeUser(PySpringModel, table=True):
    __tablename__ = "return_type_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)
    salary: float = Field(default=0.0)
    active: bool = Field(default=True)


class ReturnTypeUserRepository(CrudRepository[int, ReturnTypeUser]):
    @Query("DELETE FROM return_type_user WHERE name = :name", is_modifying=True)
    def delete_by_name(self, name: str) -> type(None): ...  # type: ignore

    @Query("SELECT salary FROM return_type_user WHERE name = :name")
    def get_salary_by_name(self, name: str) -> float: ...

    @Query("SELECT name FROM return_type_user WHERE id = :id")
    def get_name_by_id(self, id: int) -> str: ...

    @Query("SELECT active FROM return_type_user WHERE name = :name")
    def is_active(self, name: str) -> bool: ...

    @Query("SELECT age FROM return_type_user WHERE name = :name")
    def get_age_by_name(self, name: str) -> Optional[int]: ...

    @Query("SELECT * FROM return_type_user WHERE name = :name")
    def find_one_by_name(self, name: str) -> ReturnTypeUser: ...

    @Query("SELECT COUNT(*) FROM return_type_user WHERE age > :min_age")
    def count_older_than(self, min_age: int) -> int: ...


class BaseQueryReturnTypes:
    def setup_method(self):
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([ReturnTypeUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        self.repo = ReturnTypeUserRepository()

        # Seed data
        self.repo.save(ReturnTypeUser(name="Alice", email="a@e.com", age=30, salary=50000.5, active=True))
        self.repo.save(ReturnTypeUser(name="Bob", email="b@e.com", age=25, salary=40000.0, active=False))

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None
        PySpringModel._metadata = None

    # --- None return type ---

    def test_none_return_type_delete(self):
        """@Query with return type None should execute and return None."""
        result = self.repo.delete_by_name(name="Alice")
        assert result is None
        # Verify deletion actually happened
        remaining = self.repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Bob"

    # --- Scalar return types ---

    def test_float_scalar_return(self):
        """@Query returning float should work."""
        salary = self.repo.get_salary_by_name(name="Alice")
        assert isinstance(salary, float)
        assert salary == 50000.5

    def test_str_scalar_return(self):
        """@Query returning str should work."""
        name = self.repo.get_name_by_id(id=1)
        assert isinstance(name, str)
        assert name == "Alice"

    def test_bool_scalar_return(self):
        """@Query returning bool should work."""
        # SQLite returns 0/1 for booleans, so we check truthiness
        active = self.repo.is_active(name="Alice")
        assert active  # True

        inactive = self.repo.is_active(name="Bob")
        assert not inactive  # False

    def test_int_scalar_return(self):
        """@Query returning int (count) should work."""
        count = self.repo.count_older_than(min_age=28)
        assert count == 1  # Only Alice (30)

    # --- Optional scalar return ---

    def test_optional_int_returns_value(self):
        """Optional[int] should return the value when row exists."""
        age = self.repo.get_age_by_name(name="Alice")
        assert age == 30

    def test_optional_int_returns_none(self):
        """Optional[int] should return None when no row matches."""
        age = self.repo.get_age_by_name(name="Nobody")
        assert age is None

    # --- Non-optional BaseModel no result ---

    def test_non_optional_basemodel_raises_on_no_result(self):
        """Non-optional BaseModel return should raise ValueError when no row found."""
        with pytest.raises(ValueError, match="No result found for query"):
            self.repo.find_one_by_name(name="Nobody")

    def test_non_optional_basemodel_returns_result(self):
        """Non-optional BaseModel return should work when a row is found."""
        user = self.repo.find_one_by_name(name="Alice")
        assert user.name == "Alice"
        assert user.email == "a@e.com"


class BaseQueryExecutionServiceInvalidReturnType:
    """Test the invalid return type error path."""

    def setup_method(self):
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None
        PySpringModel._metadata = None

    def test_invalid_return_type_raises(self):
        """Return type that is not BaseModel, scalar, list, or None should raise."""
        def bad_func(x: int) -> dict:
            ...

        with pytest.raises(ValueError, match="Invalid return type"):
            QueryExecutionService.execute_query(
                query_template="SELECT 1",
                func=bad_func,
                kwargs={"x": 1},
                is_modifying=False,
            )


class BaseQueryExecutionServiceMissingAnnotation:
    """Test missing return annotation error."""

    def setup_method(self):
        PySpringModel.set_engine(self.engine)
        SessionContextHolder.clear()

    def teardown_method(self):
        SessionContextHolder.clear()
        PySpringModel._engine = None

    def test_missing_return_annotation_raises(self):
        """Function without return annotation should raise ValueError."""
        def no_return_func(x: int):
            ...

        with pytest.raises(ValueError, match="Missing return annotation"):
            QueryExecutionService.execute_query(
                query_template="SELECT 1",
                func=no_return_func,
                kwargs={"x": 1},
                is_modifying=False,
            )
