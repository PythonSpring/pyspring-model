from typing import List, Optional

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

    @Query("SELECT * FROM qes_user WHERE age IN :ages")
    def find_all_by_ages_in(self, ages: list[int]) -> List[QESUser]: ...

    @Query("SELECT * FROM qes_user WHERE name IN :names AND age > :min_age")
    def find_all_by_names_in_and_older_than(self, names: list[str], min_age: int) -> List[QESUser]: ...

    @Query("SELECT * FROM qes_user WHERE name = :name AND age > :min_age")
    def find_by_name_and_min_age(self, name: str, min_age: int) -> Optional[QESUser]: ...


class BaseQueryExecutionServiceParameterized:
    def setup_method(self):
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([QESUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        self.repo = QESUserRepository()

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)

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

    def test_in_query_returns_matching_results(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=25))
        self.repo.save(QESUser(name="Charlie", email="charlie@example.com", age=35))
        results = self.repo.find_all_by_names_in(names=["Alice", "Charlie"])
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"Alice", "Charlie"}

    def test_in_query_single_element_list(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=25))
        results = self.repo.find_all_by_names_in(names=["Bob"])
        assert len(results) == 1
        assert results[0].name == "Bob"

    def test_in_query_no_matches(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        results = self.repo.find_all_by_names_in(names=["Nobody", "Ghost"])
        assert len(results) == 0

    def test_in_query_all_match(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=25))
        results = self.repo.find_all_by_names_in(names=["Alice", "Bob"])
        assert len(results) == 2

    def test_in_query_with_int_list(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=25))
        self.repo.save(QESUser(name="Charlie", email="charlie@example.com", age=35))
        results = self.repo.find_all_by_ages_in(ages=[25, 35])
        assert len(results) == 2
        ages = {r.age for r in results}
        assert ages == {25, 35}

    def test_in_query_combined_with_scalar_param(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        self.repo.save(QESUser(name="Bob", email="bob@example.com", age=25))
        self.repo.save(QESUser(name="Charlie", email="charlie@example.com", age=35))
        results = self.repo.find_all_by_names_in_and_older_than(names=["Alice", "Bob", "Charlie"], min_age=28)
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"Alice", "Charlie"}

    def test_in_query_with_duplicate_values(self):
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        results = self.repo.find_all_by_names_in(names=["Alice", "Alice"])
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_parameterized_query_rejects_wrong_type(self):
        import pytest
        self.repo.save(QESUser(name="Alice", email="alice@example.com", age=30))
        with pytest.raises(TypeError, match="Invalid type for argument"):
            self.repo.find_by_name_and_min_age(name="Alice", min_age="not_an_int")
