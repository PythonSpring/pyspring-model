import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from py_spring_model import PySpringModel, Field, CrudRepository
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import CrudRepositoryImplementationService
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import FieldOperation


class TestUser(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int
    salary: float = Field(default=0.0)
    status: str = Field(default="active")
    category: str = Field(default="general")


class TestUserRepository(CrudRepository[int, TestUser]):
    # Test different field operations
    def find_all_by_age_gt(self, age: int) -> list[TestUser]: ...
    def find_all_by_age_gte(self, age: int) -> list[TestUser]: ...
    def find_all_by_age_lt(self, age: int) -> list[TestUser]: ...
    def find_all_by_age_lte(self, age: int) -> list[TestUser]: ...
    def find_all_by_name_like(self, name: str) -> list[TestUser]: ...
    def find_all_by_status_ne(self, status: str) -> list[TestUser]: ...
    def find_all_by_status_in(self, status: list[str]) -> list[TestUser]: ...
    def find_all_by_category_not_in(self, category: list[str]) -> list[TestUser]: ...
    
    # Test combinations
    def find_all_by_age_gt_and_status_in(self, age: int, status: list[str]) -> list[TestUser]: ...
    def find_all_by_salary_gte_or_category_in(self, salary: float, category: list[str]) -> list[TestUser]: ...


class TestFieldOperations:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SQLModel.metadata.create_all(self.engine)
        
        self.repository = TestUserRepository()
        self.implementation_service = CrudRepositoryImplementationService()
        
        # Create test data
        self.test_users = [
            TestUser(name="John Doe", email="john@example.com", age=25, salary=50000.0, status="active", category="employee"),
            TestUser(name="Jane Smith", email="jane@example.com", age=30, salary=60000.0, status="active", category="manager"),
            TestUser(name="Bob Johnson", email="bob@example.com", age=35, salary=70000.0, status="inactive", category="employee"),
            TestUser(name="Alice Brown", email="alice@example.com", age=40, salary=80000.0, status="pending", category="executive"),
            TestUser(name="Charlie Wilson", email="charlie@example.com", age=45, salary=90000.0, status="active", category="executive"),
        ]
        
        for user in self.test_users:
            self.repository.save(user)
        
        # Implement the queries
        self.implementation_service._implemenmt_query(self.repository.__class__)

    def test_greater_than_operation(self):
        """Test greater than operation"""
        users = self.repository.find_all_by_age_gte(age=30)
        assert len(users) == 4  # 30, 35, 40, 45
        
        # Verify all users are >= 30
        for user in users:
            assert user.age >= 30

    def test_less_than_operation(self):
        """Test less than operation"""
        users = self.repository.find_all_by_age_lt(age=35)
        assert len(users) == 2  # 25, 30
        
        # Verify all users are < 35
        for user in users:
            assert user.age < 35

    def test_less_equal_operation(self):
        """Test less than or equal operation"""
        users = self.repository.find_all_by_age_lte(age=30)
        assert len(users) == 2  # 25, 30
        
        # Verify all users are <= 30
        for user in users:
            assert user.age <= 30

    def test_like_operation(self):
        """Test LIKE operation"""
        users = self.repository.find_all_by_name_like(name="%ohn%")
        assert len(users) == 2  # John Doe, Bob Johnson
        
        # Verify all users have "ohn" in their name
        for user in users:
            assert "ohn" in user.name.lower()

    def test_not_equals_operation(self):
        """Test not equals operation"""
        users = self.repository.find_all_by_status_ne(status="active")
        assert len(users) == 2  # inactive, pending
        
        # Verify all users are not "active"
        for user in users:
            assert user.status != "active"

    def test_not_in_operation(self):
        """Test NOT IN operation"""
        users = self.repository.find_all_by_category_not_in(category=["employee", "manager"])
        assert len(users) == 2  # executive users
        
        # Verify all users are not in the excluded categories
        for user in users:
            assert user.category not in ["employee", "manager"]

    def test_combination_gt_and_in(self):
        """Test combination of greater than and IN operations"""
        users = self.repository.find_all_by_age_gt_and_status_in(age=30, status=["active", "pending"])
        assert len(users) == 2  # 40 (pending), 45 (active) - only users > 30 with active/pending status
        
        # Verify all users are > 30 and have active/pending status
        for user in users:
            assert user.age > 30
            assert user.status in ["active", "pending"]

    def test_combination_gte_or_in(self):
        """Test combination of greater equal and IN operations with OR"""
        users = self.repository.find_all_by_salary_gte_or_category_in(salary=70000.0, category=["executive"])
        assert len(users) == 3  # 70000+, 80000+, 90000+ - all users with salary >= 70000
        
        # Verify all users either have salary >= 70000 OR are executives
        for user in users:
            assert user.salary >= 70000.0 or user.category == "executive"

    def test_empty_list_in_operation(self):
        """Test IN operation with empty list returns no results"""
        users = self.repository.find_all_by_status_in(status=[])
        assert len(users) == 0

    def test_empty_list_not_in_operation(self):
        """Test NOT IN operation with empty list returns all results"""
        users = self.repository.find_all_by_category_not_in(category=[])
        assert len(users) == 5  # All users

    def test_invalid_type_for_in_operation(self):
        """Test that IN operation requires collection type"""
        with pytest.raises(ValueError, match=".*collection.*"):
            self.repository.find_all_by_status_in(status="active")  # type: ignore # Should be list 

    def test_invalid_type_for_not_in_operation(self):
        """Test that NOT IN operation requires collection type"""
        with pytest.raises(ValueError, match=".*collection.*"):
            self.repository.find_all_by_category_not_in(category="employee")  # type: ignore # Should be list

    def test_field_operation_enum_values(self):
        """Test that FieldOperation enum has correct values"""
        assert FieldOperation.IN == "in"
        assert FieldOperation.GREATER_THAN == "gt"
        assert FieldOperation.GREATER_EQUAL == "gte"
        assert FieldOperation.LESS_THAN == "lt"
        assert FieldOperation.LESS_EQUAL == "lte"
        assert FieldOperation.LIKE == "like"
        assert FieldOperation.NOT_EQUALS == "ne"
        assert FieldOperation.NOT_IN == "not_in"
        assert FieldOperation.EQUALS == "equals" 