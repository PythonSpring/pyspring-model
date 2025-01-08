import pytest
from loguru import logger
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.repository.crud_repository import CrudRepository

class User(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str

class UserRepository(CrudRepository[int,User]): ...


class TestCrudRepository:
    def setup_method(self):
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=True)
        PySpringModel._engine = self.engine
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)

    @pytest.fixture
    def user_repository(self):
        repo = UserRepository()
        return repo

    def create_test_user(self, user_repository: UserRepository):
        user = User(name="John Doe", email="john@example.com")
        user_repository.save(user)
        logger.info(f"Created user with ID: {user.id}")

    def test_did_get_model_id_type_with_class(self):
        id_type, model_type = UserRepository._get_model_id_type_with_class()
        assert id_type == int
        assert model_type == User
    

    def test_find_by_id(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        user = user_repository.find_by_id(1)
        assert user is not None
        assert user.id == 1
        assert user.name == "John Doe"

    def test_find_all(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        users = user_repository.find_all()
        assert len(users) == 1
        assert users[0].id == 1
        assert users[0].name == "John Doe"

    def test_find_by_query(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        _, user = user_repository._find_by_query({"name": "John Doe"})
        assert user is not None
        assert user.id == 1
        assert user.name == "John Doe"

        _, email_user = user_repository._find_by_query({"email": "john@example.com"})
        assert email_user is not None
        assert email_user.id == 1
        assert email_user.email == "john@example.com"

    def test_find_all_by_query(self, user_repository: UserRepository):
        john = User(name="John Doe", email="john@example.com")
        john_2 = User(name="John Doe", email="john2@example.com")
        user_repository.save(john)
        user_repository.save(john_2)
        _, users = user_repository._find_all_by_query({"name": "John Doe"})
        assert len(users) == 2
        user_1 = users[0]
        user_2 = users[1]
        assert user_1 is not None
        assert user_1.id == 1
        assert user_1.name == "John Doe"
        assert user_1.email == "john@example.com"

        assert user_2 is not None
        assert user_2.id == 2
        assert user_2.name == "John Doe"
        assert user_2.email == "john2@example.com"


    def test_delete(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        user = user_repository.find_by_id(1)
        assert user is not None
        assert user_repository.delete(user)
        assert user_repository.find_by_id(1) is None

    def test_delete_by_id(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        user = user_repository.find_by_id(1)
        assert user is not None
        assert user_repository.delete_by_id(1)
        assert user_repository.find_by_id(1) is None

    def test_delete_all(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        users = user_repository.find_all()
        assert len(users) == 1
        assert user_repository.delete_all(users)
        assert len(user_repository.find_all()) == 0

    def test_delete_all_by_ids(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        assert user_repository.delete_all_by_ids([1])
        assert user_repository.find_by_id(1) is None
    
    def test_upsert_for_existing_user(self, user_repository: UserRepository):
        self.create_test_user(user_repository)
        user = user_repository.find_by_id(1)
        assert user is not None
        user.name = "William Chen"
        user.email = "william.chen@example.com"
        assert user_repository.upsert(user, {"id": 1})
        updated_user = user_repository.find_by_id(1)
        assert updated_user is not None
        assert updated_user.name == "William Chen"
        assert updated_user.email == "william.chen@example.com"


    def test_upsert_for_new_user(self, user_repository: UserRepository):
        user = User(name="John Doe", email="john@example.com")
        assert user_repository.upsert(user, {"name": "John Doe"})
        new_user = user_repository.find_by_id(1)
        assert new_user is not None
        assert new_user.name == "John Doe"
        assert new_user.email == "john@example.com"