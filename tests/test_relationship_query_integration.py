"""
Integration tests for relationship query builder.
Tests: one-to-many joins, reverse direction, mixed fields, all query types,
operation suffixes on relationship fields, deduplication.
"""
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from py_spring_model import PySpringModel, Field, Relationship, CrudRepository
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


# ---- Models ----

class Department(PySpringModel, table=True):
    __tablename__ = "rel_int_department"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    employees: list["Employee"] = Relationship(back_populates="department")


class Employee(PySpringModel, table=True):
    __tablename__ = "rel_int_employee"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    role: str = ""
    salary: int = 0
    department_id: Optional[int] = Field(default=None, foreign_key="rel_int_department.id")
    department: Optional[Department] = Relationship(back_populates="employees")


# ---- Repositories ----

class DepartmentRepository(CrudRepository[int, Department]):
    # Simple relationship filter
    def find_all_by_employees_role(self, role: str) -> list[Department]: ...
    # Relationship field with operation suffix
    def find_all_by_employees_salary_gte(self, salary: int) -> list[Department]: ...
    # Relationship field with CONTAINS
    def find_all_by_employees_name_contains(self, name: str) -> list[Department]: ...
    # Mixed: relationship + direct column
    def find_all_by_employees_role_and_name(self, role: str, name: str) -> list[Department]: ...
    # Count with relationship
    def count_by_employees_role(self, role: str) -> int: ...
    # Exists with relationship
    def exists_by_employees_role(self, role: str) -> bool: ...
    # Delete with relationship
    def delete_all_by_employees_role(self, role: str) -> int: ...


class EmployeeRepository(CrudRepository[int, Employee]):
    # Reverse: child filtered by parent attribute
    def find_all_by_department_name(self, name: str) -> list[Employee]: ...


# ---- Test class ----

class TestRelationshipQueryIntegration:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.dept_repo = DepartmentRepository()
        self.emp_repo = EmployeeRepository()
        self.service = CrudRepositoryImplementationService()

        # Seed data
        eng = Department(name="Engineering")
        sales = Department(name="Sales")
        self.dept_repo.save(eng)
        self.dept_repo.save(sales)

        session = SessionContextHolder.get_or_create_session()
        session.add(Employee(name="Alice", role="engineer", salary=100, department_id=eng.id))
        session.add(Employee(name="Bob", role="engineer", salary=150, department_id=eng.id))
        session.add(Employee(name="Charlie", role="manager", salary=200, department_id=eng.id))
        session.add(Employee(name="Diana", role="sales_rep", salary=80, department_id=sales.id))
        session.add(Employee(name="Eve", role="sales_rep", salary=90, department_id=sales.id))
        session.commit()

        self.service._implemenmt_query(DepartmentRepository)
        self.service._implemenmt_query(EmployeeRepository)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    # --- SELECT queries ---

    def test_find_all_by_relationship_field(self):
        """find_all_by_employees_role should return departments with matching employees."""
        results = self.dept_repo.find_all_by_employees_role(role="engineer")
        assert len(results) == 1
        assert results[0].name == "Engineering"

    def test_find_all_by_relationship_field_no_duplicates(self):
        """Engineering has 2 engineers; result should still be 1 department (DISTINCT)."""
        results = self.dept_repo.find_all_by_employees_role(role="engineer")
        assert len(results) == 1

    def test_find_all_by_relationship_field_no_match(self):
        results = self.dept_repo.find_all_by_employees_role(role="ceo")
        assert len(results) == 0

    def test_find_all_by_relationship_with_operation_suffix(self):
        """salary_gte=150 -> Bob(150) in Engineering, Charlie(200) in Engineering."""
        results = self.dept_repo.find_all_by_employees_salary_gte(salary=150)
        assert len(results) == 1
        assert results[0].name == "Engineering"

    def test_find_all_by_relationship_with_contains(self):
        results = self.dept_repo.find_all_by_employees_name_contains(name="li")
        # "Alice" and "Charlie" both contain "li" -> Engineering
        assert len(results) == 1
        assert results[0].name == "Engineering"

    def test_find_all_by_mixed_relationship_and_direct(self):
        """employees_role='engineer' AND name='Engineering'."""
        results = self.dept_repo.find_all_by_employees_role_and_name(role="engineer", name="Engineering")
        assert len(results) == 1
        assert results[0].name == "Engineering"

    def test_find_all_by_mixed_no_match(self):
        """employees_role='engineer' AND name='Sales' -> no match."""
        results = self.dept_repo.find_all_by_employees_role_and_name(role="engineer", name="Sales")
        assert len(results) == 0

    # --- Reverse direction ---

    def test_reverse_direction_child_filtered_by_parent(self):
        """Employees whose department name is 'Sales'."""
        results = self.emp_repo.find_all_by_department_name(name="Sales")
        assert len(results) == 2
        names = sorted(e.name for e in results)
        assert names == ["Diana", "Eve"]

    # --- COUNT ---

    def test_count_by_relationship_field(self):
        count = self.dept_repo.count_by_employees_role(role="engineer")
        assert count == 1  # 1 department with engineers

    def test_count_by_relationship_field_no_match(self):
        count = self.dept_repo.count_by_employees_role(role="ceo")
        assert count == 0

    # --- EXISTS ---

    def test_exists_by_relationship_field_true(self):
        assert self.dept_repo.exists_by_employees_role(role="engineer") is True

    def test_exists_by_relationship_field_false(self):
        assert self.dept_repo.exists_by_employees_role(role="ceo") is False

    # --- DELETE ---

    def test_delete_all_by_relationship_field(self):
        """Delete departments that have sales_rep employees."""
        count = self.dept_repo.delete_all_by_employees_role(role="sales_rep")
        assert count == 1  # Sales department deleted
        remaining = self.dept_repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Engineering"
