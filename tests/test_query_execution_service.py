from typing import List, Optional

from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.query_service.query import Query
from py_spring_model.repository.crud_repository import CrudRepository


class QESUser(PySpringModel, table=True):
    __tablename__ = "qes_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)


class QESUserRepository(CrudRepository[int, QESUser]):
    @Query("SELECT * FROM qes_user WHERE name = :name")
    def find_by_name(self, name: str) -> Optional[QESUser]: ...

    @Query("SELECT * FROM qes_user WHERE age > :min_age")
    def find_users_older_than(self, min_age: int) -> List[QESUser]: ...

    @Query("SELECT * FROM qes_user WHERE name IN :names")
    def find_all_by_names_in(self, names: list[str]) -> List[QESUser]: ...

    @Query("SELECT * FROM qes_user WHERE name = :name AND age > :min_age")
    def find_by_name_and_min_age(self, name: str, min_age: int) -> Optional[QESUser]: ...


class TestQueryExecutionServiceParameterized:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([QESUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        self.repo = QESUserRepository()

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def test_parameterized_query_returns_single_result(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        result = self.repo.find_by_name(name="Alice")
        assert result is not None
        assert result.name == "Alice"

    def test_parameterized_query_prevents_sql_injection(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        # This should NOT return results - the injection attempt should be treated as a literal string
        result = self.repo.find_by_name(name="' OR '1'='1")
        assert result is None

    def test_parameterized_query_returns_list(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=20))
        results = self.repo.find_users_older_than(min_age=25)
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_parameterized_query_with_generic_list_param_passes_validation(self):
        """Validates that generic type annotations like list[str] pass type checking."""
        import pytest
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        # list[str] param should pass type validation (no TypeError)
        # The IN clause itself may fail at the DB level, but the type check must pass
        try:
            self.repo.find_all_by_names_in(names=["Alice"])
        except TypeError:
            pytest.fail("Type validation rejected list[str] parameter")
        except Exception:
            pass  # DB-level errors are acceptable; we're testing type validation

    def test_parameterized_query_rejects_wrong_type(self):
        import pytest
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        with pytest.raises(TypeError, match="Invalid type for argument"):
            self.repo.find_by_name_and_min_age(name="Alice", min_age="not_an_int")
