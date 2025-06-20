

from loguru import logger
from pydantic import BaseModel
import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from py_spring_model import PySpringModel, Field, CrudRepository, Query
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import CrudRepositoryImplementationService
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import _MetodQueryBuilder


class User(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str

class UserView(BaseModel):
    name: str

class UserRepository(CrudRepository[int,User]):
    def find_by_name(self, name: str) -> User: ...
    @Query("SELECT * FROM user WHERE name = {name}")
    def query_uery_by_name(self, name: str) -> User: ...

    @Query("SELECT * FROM user WHERE name = {name}")
    def query_user_view_by_name(self, name: str) -> UserView: ...
    

class TestQuery:
    def setup_method(self):
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=True)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear_session()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear_session()

    @pytest.fixture
    def user_repository(self):
        repo = UserRepository()
        return repo
    
    @pytest.fixture
    def implementation_service(self) -> CrudRepositoryImplementationService:
        return CrudRepositoryImplementationService()
    
    def test_query_single_annotation(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_name").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"name": "John Doe"})
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email FROM "user" WHERE "user".name = :name_1'

    def test_query_and_annotation(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_name_and_email").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"name": "John Doe", "email": "john@example.com"})
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email FROM "user" WHERE "user".email = :email_1 AND "user".name = :name_1'

    def test_query_or_annotation(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_name_or_email").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"name": "John Doe", "email": "john@example.com"})
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email FROM "user" WHERE "user".email = :email_1 OR "user".name = :name_1'

    def test_did_implement_query(self, user_repository: UserRepository, implementation_service: CrudRepositoryImplementationService):
        user = User(name="John Doe", email="john@example.com")
        user_repository.save(user)
        assert user_repository.find_by_name("John Doe") is None
        implementation_service._implemenmt_query(user_repository.__class__)
        queryed_user = user_repository.find_by_name(name = "John Doe")
        assert queryed_user.model_dump() == user.model_dump()

    
    def test_query_decorator_did_implement_query(self, user_repository: UserRepository, implementation_service: CrudRepositoryImplementationService):
        test_user = User(name="name", email="email")
        user_repository.save(test_user)
        user = user_repository.query_uery_by_name(name= "name")
        assert user.model_dump() == test_user.model_dump()


    def test_query_decorator_did_implement_query_with_view(self, user_repository: UserRepository, implementation_service: CrudRepositoryImplementationService):
        test_user = User(name="name", email="email")
        user_repository.save(test_user)
        user_view = user_repository.query_user_view_by_name(name= "name")
        assert user_view.name == "name"

    def test_query_uery_by_name_missing_argument(self, user_repository: UserRepository):
        with pytest.raises(ValueError, match="Missing required argument: name"):
            user_repository.query_uery_by_name() # type: ignore

    def test_query_uery_by_name_invalid_argument_type(self, user_repository: UserRepository):
        with pytest.raises(TypeError, match=".*"):
            user_repository.query_uery_by_name(name=123)  # `name` should be a string, not an integer # type: ignore

    def test_query_user_view_by_name_missing_argument(self, user_repository: UserRepository):
        with pytest.raises(ValueError, match="Missing required argument: name"):
            user_repository.query_user_view_by_name() # type: ignore

    def test_query_user_view_by_name_invalid_argument_type(self, user_repository: UserRepository):
        with pytest.raises(ValueError, match=".*"):
            user_repository.query_user_view_by_name(name=None)  # `name` should not be None # type: ignore

        
        
    



