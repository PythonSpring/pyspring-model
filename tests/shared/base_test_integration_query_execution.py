"""
Integration tests for query execution gaps:
1. is_null / is_not_null field operations against a real database
2. count_by / exists_by / delete_by with field operations (gt, in, etc.)
3. get_by_* prefix behaving the same as find_by_*
"""

from typing import Optional

import pytest
from sqlmodel import SQLModel

from py_spring_model import PySpringModel, Field, CrudRepository
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


# ---------------------------------------------------------------------------
# Model – uses Optional[str] for nickname so we can test IS NULL / IS NOT NULL
# ---------------------------------------------------------------------------
class NullCheckUser(PySpringModel, table=True):
    __tablename__ = "null_check_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)
    salary: float = Field(default=0.0)
    status: str = Field(default="active")
    nickname: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Repository – is_null / is_not_null
# ---------------------------------------------------------------------------
class NullCheckUserRepository(CrudRepository[int, NullCheckUser]):
    def find_all_by_nickname_is_null(self) -> list[NullCheckUser]: ...
    def find_all_by_nickname_is_not_null(self) -> list[NullCheckUser]: ...
    def find_all_by_nickname_is_null_and_status(self, status: str) -> list[NullCheckUser]: ...
    def find_all_by_nickname_is_not_null_and_age_gt(self, age: int) -> list[NullCheckUser]: ...


class BaseIsNullIsNotNull:
    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.repo = NullCheckUserRepository()
        self.service = CrudRepositoryImplementationService()

        self.repo.save(NullCheckUser(name="Alice", email="alice@e.com", age=25, status="active", nickname="Ali"))
        self.repo.save(NullCheckUser(name="Bob", email="bob@e.com", age=30, status="active", nickname=None))
        self.repo.save(NullCheckUser(name="Charlie", email="charlie@e.com", age=35, status="inactive", nickname="Chuck"))
        self.repo.save(NullCheckUser(name="Diana", email="diana@e.com", age=40, status="active", nickname=None))
        self.repo.save(NullCheckUser(name="Eve", email="eve@e.com", age=45, status="inactive", nickname=None))

        self.service._implemenmt_query(self.repo.__class__)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)

    def test_is_null_returns_users_without_nickname(self):
        users = self.repo.find_all_by_nickname_is_null()
        assert len(users) == 3  # Bob, Diana, Eve
        for user in users:
            assert user.nickname is None

    def test_is_not_null_returns_users_with_nickname(self):
        users = self.repo.find_all_by_nickname_is_not_null()
        assert len(users) == 2  # Alice, Charlie
        for user in users:
            assert user.nickname is not None

    def test_is_null_combined_with_equals(self):
        """IS NULL combined with AND equality check"""
        users = self.repo.find_all_by_nickname_is_null_and_status(status="active")
        assert len(users) == 2  # Bob, Diana (nickname is null AND status is active)
        for user in users:
            assert user.nickname is None
            assert user.status == "active"

    def test_is_not_null_combined_with_gt(self):
        """IS NOT NULL combined with AND greater-than"""
        users = self.repo.find_all_by_nickname_is_not_null_and_age_gt(age=30)
        assert len(users) == 1  # Charlie (nickname not null AND age > 30)
        assert users[0].name == "Charlie"

    def test_is_null_when_all_have_values(self):
        """IS NULL should return empty when all rows have non-null values for the field"""
        # Clear and re-seed with all non-null nicknames
        self.repo.delete_all(self.repo.find_all())
        self.repo.save(NullCheckUser(name="X", email="x@e.com", nickname="xx"))
        self.repo.save(NullCheckUser(name="Y", email="y@e.com", nickname="yy"))
        users = self.repo.find_all_by_nickname_is_null()
        assert len(users) == 0

    def test_is_not_null_when_all_are_null(self):
        """IS NOT NULL should return empty when all rows have null values for the field"""
        self.repo.delete_all(self.repo.find_all())
        self.repo.save(NullCheckUser(name="X", email="x@e.com", nickname=None))
        self.repo.save(NullCheckUser(name="Y", email="y@e.com", nickname=None))
        users = self.repo.find_all_by_nickname_is_not_null()
        assert len(users) == 0


# ---------------------------------------------------------------------------
# Model for count_by / exists_by / delete_by with field operations
# ---------------------------------------------------------------------------
class OpUser(PySpringModel, table=True):
    __tablename__ = "op_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)
    status: str = Field(default="active")
    category: str = Field(default="general")


# ---------------------------------------------------------------------------
# Repository – count/exists/delete with field operations
# ---------------------------------------------------------------------------
class FieldOpQueryRepository(CrudRepository[int, OpUser]):
    # count_by with field operations
    def count_by_age_gt(self, age: int) -> int: ...
    def count_by_age_gte(self, age: int) -> int: ...
    def count_by_age_lt(self, age: int) -> int: ...
    def count_by_status_in(self, status: list[str]) -> int: ...
    def count_by_age_gt_and_status(self, age: int, status: str) -> int: ...

    # exists_by with field operations
    def exists_by_age_gt(self, age: int) -> bool: ...
    def exists_by_age_lt(self, age: int) -> bool: ...
    def exists_by_status_in(self, status: list[str]) -> bool: ...
    def exists_by_name_contains(self, name: str) -> bool: ...

    # delete_by with field operations
    def delete_by_age_gt(self, age: int) -> int: ...
    def delete_all_by_age_lt(self, age: int) -> int: ...
    def delete_all_by_status_in(self, status: list[str]) -> int: ...


class BaseCountExistsDeleteWithFieldOperations:
    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.repo = FieldOpQueryRepository()
        self.service = CrudRepositoryImplementationService()

        self.repo.save(OpUser(name="Alice", email="a@e.com", age=20, status="active", category="junior"))
        self.repo.save(OpUser(name="Bob", email="b@e.com", age=30, status="active", category="mid"))
        self.repo.save(OpUser(name="Charlie", email="c@e.com", age=40, status="inactive", category="senior"))
        self.repo.save(OpUser(name="Diana", email="d@e.com", age=50, status="pending", category="senior"))
        self.repo.save(OpUser(name="Eve Johnson", email="e@e.com", age=60, status="active", category="executive"))

        self.service._implemenmt_query(self.repo.__class__)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)

    # -----------------------------------------------------------------------
    # count_by with field operations
    # -----------------------------------------------------------------------
    def test_count_by_age_gt(self):
        assert self.repo.count_by_age_gt(age=30) == 3  # 40, 50, 60

    def test_count_by_age_gte(self):
        assert self.repo.count_by_age_gte(age=30) == 4  # 30, 40, 50, 60

    def test_count_by_age_lt(self):
        assert self.repo.count_by_age_lt(age=30) == 1  # 20

    def test_count_by_status_in(self):
        assert self.repo.count_by_status_in(status=["active", "pending"]) == 4  # Alice, Bob, Diana, Eve

    def test_count_by_field_op_and_equals(self):
        assert self.repo.count_by_age_gt_and_status(age=30, status="active") == 1  # Eve (age 60, active)

    def test_count_by_returns_zero_when_no_match(self):
        assert self.repo.count_by_age_gt(age=100) == 0

    # -----------------------------------------------------------------------
    # exists_by with field operations
    # -----------------------------------------------------------------------
    def test_exists_by_age_gt_true(self):
        assert self.repo.exists_by_age_gt(age=50) is True  # Eve (60)

    def test_exists_by_age_gt_false(self):
        assert self.repo.exists_by_age_gt(age=100) is False

    def test_exists_by_age_lt_true(self):
        assert self.repo.exists_by_age_lt(age=25) is True  # Alice (20)

    def test_exists_by_age_lt_false(self):
        assert self.repo.exists_by_age_lt(age=10) is False

    def test_exists_by_status_in_true(self):
        assert self.repo.exists_by_status_in(status=["pending"]) is True

    def test_exists_by_status_in_false(self):
        assert self.repo.exists_by_status_in(status=["archived"]) is False

    def test_exists_by_name_contains(self):
        assert self.repo.exists_by_name_contains(name="Johnson") is True  # Eve Johnson
        assert self.repo.exists_by_name_contains(name="Zzz") is False

    # -----------------------------------------------------------------------
    # delete_by / delete_all_by with field operations
    # -----------------------------------------------------------------------
    def test_delete_by_age_gt(self):
        count = self.repo.delete_by_age_gt(age=50)
        assert count == 1  # Eve (60)
        assert self.repo.count() == 4

    def test_delete_all_by_age_lt(self):
        count = self.repo.delete_all_by_age_lt(age=35)
        assert count == 2  # Alice (20), Bob (30)
        remaining = self.repo.find_all()
        assert len(remaining) == 3
        for user in remaining:
            assert user.age >= 35

    def test_delete_all_by_status_in(self):
        count = self.repo.delete_all_by_status_in(status=["inactive", "pending"])
        assert count == 2  # Charlie, Diana
        remaining = self.repo.find_all()
        assert len(remaining) == 3
        for user in remaining:
            assert user.status not in ["inactive", "pending"]

    def test_delete_with_no_matches(self):
        count = self.repo.delete_by_age_gt(age=999)
        assert count == 0
        assert self.repo.count() == 5


# ---------------------------------------------------------------------------
# Model for get_by_* prefix tests
# ---------------------------------------------------------------------------
class PrefixUser(PySpringModel, table=True):
    __tablename__ = "prefix_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=0)
    status: str = Field(default="active")


# ---------------------------------------------------------------------------
# Repository – get_by / get_all_by mirrors of find_by / find_all_by
# ---------------------------------------------------------------------------
class PrefixUserRepository(CrudRepository[int, PrefixUser]):
    # get_by_* (single result)
    def get_by_name(self, name: str) -> PrefixUser: ...
    def get_by_name_and_email(self, name: str, email: str) -> PrefixUser: ...

    # get_all_by_* (multiple results)
    def get_all_by_status(self, status: str) -> list[PrefixUser]: ...
    def get_all_by_age_gt(self, age: int) -> list[PrefixUser]: ...
    def get_all_by_status_in(self, status: list[str]) -> list[PrefixUser]: ...

    # find_by_* equivalents for comparison
    def find_by_name(self, name: str) -> PrefixUser: ...
    def find_all_by_status(self, status: str) -> list[PrefixUser]: ...


class BaseGetByPrefix:
    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.repo = PrefixUserRepository()
        self.service = CrudRepositoryImplementationService()

        self.repo.save(PrefixUser(name="Alice", email="alice@e.com", age=25, status="active"))
        self.repo.save(PrefixUser(name="Bob", email="bob@e.com", age=35, status="active"))
        self.repo.save(PrefixUser(name="Charlie", email="charlie@e.com", age=45, status="inactive"))

        self.service._implemenmt_query(self.repo.__class__)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)

    def test_get_by_returns_single_result(self):
        user = self.repo.get_by_name(name="Alice")
        assert user is not None
        assert user.name == "Alice"

    def test_get_by_returns_none_when_not_found(self):
        user = self.repo.get_by_name(name="Nobody")
        assert user is None

    def test_get_by_with_and(self):
        user = self.repo.get_by_name_and_email(name="Alice", email="alice@e.com")
        assert user is not None
        assert user.name == "Alice"
        assert user.email == "alice@e.com"

    def test_get_by_matches_find_by_result(self):
        get_result = self.repo.get_by_name(name="Bob")
        find_result = self.repo.find_by_name(name="Bob")
        assert get_result is not None
        assert find_result is not None
        assert get_result.model_dump() == find_result.model_dump()

    def test_get_all_by_returns_multiple(self):
        users = self.repo.get_all_by_status(status="active")
        assert len(users) == 2  # Alice, Bob
        for user in users:
            assert user.status == "active"

    def test_get_all_by_matches_find_all_by_result(self):
        get_results = self.repo.get_all_by_status(status="active")
        find_results = self.repo.find_all_by_status(status="active")
        assert len(get_results) == len(find_results)
        get_names = sorted(u.name for u in get_results)
        find_names = sorted(u.name for u in find_results)
        assert get_names == find_names

    def test_get_all_by_with_field_operation(self):
        users = self.repo.get_all_by_age_gt(age=30)
        assert len(users) == 2  # Bob (35), Charlie (45)
        for user in users:
            assert user.age > 30

    def test_get_all_by_with_in_operation(self):
        users = self.repo.get_all_by_status_in(status=["active", "inactive"])
        assert len(users) == 3  # all users

    def test_get_all_by_returns_empty_when_no_match(self):
        users = self.repo.get_all_by_status(status="archived")
        assert len(users) == 0
