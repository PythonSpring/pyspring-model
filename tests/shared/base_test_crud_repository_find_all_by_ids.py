"""
Tests for CrudRepository.find_all_by_ids().
"""

from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.repository.crud_repository import CrudRepository


class FindByIdsUser(PySpringModel, table=True):
    __tablename__ = "find_by_ids_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


class FindByIdsUserRepository(CrudRepository[int, FindByIdsUser]):
    ...


class BaseFindAllByIds:
    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)
        self.repo = FindByIdsUserRepository()

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    def test_find_all_by_ids_returns_matching_entities(self):
        u1 = self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        u2 = self.repo.save(FindByIdsUser(name="Bob", email="b@e.com"))
        u3 = self.repo.save(FindByIdsUser(name="Charlie", email="c@e.com"))

        results = self.repo.find_all_by_ids([u1.id, u3.id])
        assert len(results) == 2
        names = sorted(r.name for r in results)
        assert names == ["Alice", "Charlie"]

    def test_find_all_by_ids_returns_empty_for_no_match(self):
        self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        results = self.repo.find_all_by_ids([999, 1000])
        assert len(results) == 0

    def test_find_all_by_ids_with_empty_list(self):
        self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        results = self.repo.find_all_by_ids([])
        assert len(results) == 0

    def test_find_all_by_ids_with_single_id(self):
        u1 = self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        results = self.repo.find_all_by_ids([u1.id])
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_find_all_by_ids_returns_all_when_all_match(self):
        u1 = self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        u2 = self.repo.save(FindByIdsUser(name="Bob", email="b@e.com"))
        results = self.repo.find_all_by_ids([u1.id, u2.id])
        assert len(results) == 2

    def test_find_all_by_ids_partial_match(self):
        """Some IDs exist, some don't — should return only matching."""
        u1 = self.repo.save(FindByIdsUser(name="Alice", email="a@e.com"))
        results = self.repo.find_all_by_ids([u1.id, 999])
        assert len(results) == 1
        assert results[0].name == "Alice"
