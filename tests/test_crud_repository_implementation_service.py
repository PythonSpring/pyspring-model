

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
    status: str = Field(default="active")
    category: str = Field(default="general")

class UserView(BaseModel):
    name: str

class UserRepository(CrudRepository[int,User]):
    def find_by_name(self, name: str) -> User: ...
    def find_all_by_status_in(self, status: list[str]) -> list[User]: ...
    def find_all_by_id_in_and_name(self, id: list[int], name: str) -> list[User]: ...
    def find_all_by_status_in_or_category_in(self, status: list[str], category: list[str]) -> list[User]: ...
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
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email, "user".status, "user".category FROM "user" WHERE "user".name = :name_1'

    def test_query_and_annotation(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_name_and_email").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"name": "John Doe", "email": "john@example.com"})
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email, "user".status, "user".category FROM "user" WHERE "user".email = :email_1 AND "user".name = :name_1'

    def test_query_or_annotation(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_name_or_email").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"name": "John Doe", "email": "john@example.com"})
        assert str(statement).replace("\n", "") == 'SELECT "user".id, "user".name, "user".email, "user".status, "user".category FROM "user" WHERE "user".email = :email_1 OR "user".name = :name_1'

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

    def test_in_operator_single_field(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_status_in").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"status": ["active", "pending"]})
        assert "IN" in str(statement).upper()
        assert "status" in str(statement).lower()

    def test_in_operator_with_and(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_id_in_and_name").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"id": [1, 2, 3], "name": "John"})
        assert "IN" in str(statement).upper()
        assert "AND" in str(statement).upper()

    def test_in_operator_with_or(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_status_in_or_category_in").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"status": ["active"], "category": ["premium"]})
        assert "IN" in str(statement).upper()
        assert "OR" in str(statement).upper()

    def test_in_operator_empty_list(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_status_in").parse_query()
        statement = implementation_service._get_sql_statement(User, parsed_query, {"status": []})
        # Empty list should result in a condition that's always false
        assert "IS NULL" in str(statement) or "= NULL" in str(statement)

    def test_in_operator_invalid_type(self, implementation_service: CrudRepositoryImplementationService):
        parsed_query = _MetodQueryBuilder("find_by_status_in").parse_query()
        with pytest.raises(ValueError, match="Parameter for IN operation must be a collection"):
            implementation_service._get_sql_statement(User, parsed_query, {"status": "not_a_list"})

    def test_in_operator_implementation(self, user_repository: UserRepository, implementation_service: CrudRepositoryImplementationService):
        # Create test users
        user1 = User(name="John", email="john@example.com", status="active", category="premium")
        user2 = User(name="Jane", email="jane@example.com", status="pending", category="premium")
        user3 = User(name="Bob", email="bob@example.com", status="active", category="basic")
        
        user_repository.save(user1)
        user_repository.save(user2)
        user_repository.save(user3)
        
        # Implement the query
        implementation_service._implemenmt_query(user_repository.__class__)
        
        # Test IN operator
        active_users = user_repository.find_all_by_status_in(status=["active"])
        assert len(active_users) == 2
        assert all(user.status == "active" for user in active_users)
        
        # Test IN with AND
        premium_active_users = user_repository.find_all_by_id_in_and_name(id=[user1.id, user2.id], name="John")
        assert len(premium_active_users) == 1
        assert premium_active_users[0].name == "John"
        
        # Test IN with OR
        active_or_premium = user_repository.find_all_by_status_in_or_category_in(status=["active"], category=["premium"])
        assert len(active_or_premium) == 3  # All users are either active or premium

    def test_in_operator_empty_list_returns_no_results(self, user_repository: UserRepository, implementation_service: CrudRepositoryImplementationService):
        user = User(name="John", email="john@example.com", status="active")
        user_repository.save(user)
        
        implementation_service._implemenmt_query(user_repository.__class__)
        
        # Empty list should return no results
        results = user_repository.find_all_by_status_in(status=[])
        assert len(results) == 0

    def test_parameter_field_mapping_simple(self, implementation_service: CrudRepositoryImplementationService):
        """Test that parameter field mapping works with exact name matching and plural support"""
        # Test case 1: Exact match
        param_names = ['name', 'age']
        field_names = ['name', 'age']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'name': 'name', 'age': 'age'}
        
        # Test case 2: Different order but same names
        param_names = ['age', 'name']
        field_names = ['name', 'age']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'age': 'age', 'name': 'name'}
        
        # Test case 3: Plural parameters mapping to singular fields
        param_names = ['names', 'ages']
        field_names = ['name', 'age']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'names': 'name', 'ages': 'age'}
        
        # Test case 4: Mixed singular and plural
        param_names = ['name', 'ages']
        field_names = ['name', 'age']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'name': 'name', 'ages': 'age'}

    def test_parameter_field_mapping_validation(self, implementation_service: CrudRepositoryImplementationService):
        """Test that parameter field mapping properly validates and reports errors"""
        # Test case 1: Unmatched parameters (no exact match or plural form)
        with pytest.raises(ValueError, match="Unmatched parameters"):
            implementation_service._create_parameter_field_mapping(['username'], ['name'])
        
        # Test case 2: Parameter that can't be mapped to plural (ambiguous case)
        # This should work because 'statuses' exists as an exact match
        mapping = implementation_service._create_parameter_field_mapping(['statuses'], ['status', 'statuses'])
        assert mapping == {'statuses': 'statuses'}
        
        # Test case 3: Single character ending with 's' (should not be treated as plural)
        with pytest.raises(ValueError, match="Unmatched parameters"):
            implementation_service._create_parameter_field_mapping(['s'], ['name'])

    def test_parameter_field_mapping_edge_cases(self, implementation_service: CrudRepositoryImplementationService):
        """Test edge cases in parameter field mapping"""
        # Test case 1: Single parameter
        param_names = ['name']
        field_names = ['name']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'name': 'name'}
        
        # Test case 2: Empty lists
        param_names = []
        field_names = []
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {}
        
        # Test case 3: Parameter ending with 's' but not plural (like 'status')
        param_names = ['status']
        field_names = ['status']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'status': 'status'}
        
        # Test case 4: Plural of word ending with 's' (like 'statuses')
        param_names = ['statuses']
        field_names = ['status']
        mapping = implementation_service._create_parameter_field_mapping(param_names, field_names)
        assert mapping == {'statuses': 'status'}