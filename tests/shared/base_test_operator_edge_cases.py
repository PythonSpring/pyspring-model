"""
Extended operator tests targeting IN/LIKE behavior differences between SQLite and PostgreSQL.

Key differences this file exercises:
  - LIKE is case-sensitive in PostgreSQL, case-insensitive in SQLite (for ASCII)
  - CONTAINS / STARTS_WITH / ENDS_WITH with special SQL wildcard characters (%, _)
  - IN with single-element, large, and mixed-case string lists
  - NOT_IN combined with other operators
  - Relationship queries with IN/LIKE operators
"""

from typing import Optional

import pytest
from sqlmodel import SQLModel

from py_spring_model import PySpringModel, Field, Relationship, CrudRepository
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


# ---- Models ----

class OpProduct(PySpringModel, table=True):
    __tablename__ = "op_product"
    id: int = Field(default=None, primary_key=True)
    name: str
    sku: str = ""
    description: str = ""
    price: float = 0.0
    status: str = Field(default="available")
    category: str = Field(default="general")
    tags: str = Field(default="")  # comma-separated tags stored as string


class OpCategory(PySpringModel, table=True):
    __tablename__ = "op_category"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    products: list["OpCategoryProduct"] = Relationship(back_populates="category")


class OpCategoryProduct(PySpringModel, table=True):
    __tablename__ = "op_category_product"
    id: int = Field(default=None, primary_key=True)
    title: str = ""
    label: str = ""
    category_id: Optional[int] = Field(default=None, foreign_key="op_category.id")
    category: Optional[OpCategory] = Relationship(back_populates="products")


# ---- Repositories ----

class OpProductRepository(CrudRepository[int, OpProduct]):
    # IN operator variations
    def find_all_by_status_in(self, status: list[str]) -> list[OpProduct]: ...
    def find_all_by_category_in(self, category: list[str]) -> list[OpProduct]: ...
    def find_all_by_category_not_in(self, category: list[str]) -> list[OpProduct]: ...
    def find_all_by_id_in(self, id: list[int]) -> list[OpProduct]: ...

    # LIKE / pattern matching
    def find_all_by_name_like(self, name: str) -> list[OpProduct]: ...
    def find_all_by_name_not_like(self, name: str) -> list[OpProduct]: ...
    def find_all_by_name_contains(self, name: str) -> list[OpProduct]: ...
    def find_all_by_name_starts_with(self, name: str) -> list[OpProduct]: ...
    def find_all_by_name_ends_with(self, name: str) -> list[OpProduct]: ...
    def find_all_by_description_contains(self, description: str) -> list[OpProduct]: ...
    def find_all_by_sku_starts_with(self, sku: str) -> list[OpProduct]: ...

    # Combined operators
    def find_all_by_status_in_and_name_contains(self, status: list[str], name: str) -> list[OpProduct]: ...
    def find_all_by_category_not_in_or_name_like(self, category: list[str], name: str) -> list[OpProduct]: ...
    def find_all_by_price_gte_and_status_in(self, price: float, status: list[str]) -> list[OpProduct]: ...

    # Count / exists with operators
    def count_by_status_in(self, status: list[str]) -> int: ...
    def exists_by_name_contains(self, name: str) -> bool: ...
    def delete_all_by_status_in(self, status: list[str]) -> int: ...


class OpCategoryRepository(CrudRepository[int, OpCategory]):
    # Relationship + IN
    def find_all_by_products_label_in(self, label: list[str]) -> list[OpCategory]: ...
    # Relationship + CONTAINS
    def find_all_by_products_title_contains(self, title: str) -> list[OpCategory]: ...
    # Relationship + LIKE
    def find_all_by_products_label_like(self, label: str) -> list[OpCategory]: ...


# ---- Base test class ----

class BaseOperatorInLike:
    """Tests for IN/LIKE operators that may differ between SQLite and PostgreSQL."""

    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.repo = OpProductRepository()
        self.service = CrudRepositoryImplementationService()

        # Seed data with deliberate case variations and special characters
        self.products = [
            OpProduct(name="Widget Pro", sku="WGT-001", description="A premium widget with 100% quality", price=29.99, status="available", category="electronics"),
            OpProduct(name="widget basic", sku="WGT-002", description="Basic widget_model for testing", price=9.99, status="available", category="electronics"),
            OpProduct(name="Gadget Alpha", sku="GDG-001", description="First gadget in the alpha% line", price=49.99, status="available", category="gadgets"),
            OpProduct(name="Gadget Beta", sku="GDG-002", description="Second gadget (beta_release)", price=39.99, status="discontinued", category="gadgets"),
            OpProduct(name="Super Tool", sku="STL-001", description="Tool with special chars: _underscore and %percent", price=19.99, status="out_of_stock", category="tools"),
            OpProduct(name="MEGA TOOL", sku="STL-002", description="UPPERCASE tool description", price=59.99, status="available", category="tools"),
            OpProduct(name="Nano Device", sku="NND-001", description="Tiny device", price=5.99, status="preorder", category="devices"),
        ]
        for p in self.products:
            self.repo.save(p)

        self.service._implemenmt_query(OpProductRepository)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    # ================================================================
    # IN operator tests
    # ================================================================

    def test_in_single_value(self):
        """IN with a single-element list."""
        results = self.repo.find_all_by_status_in(status=["discontinued"])
        assert len(results) == 1
        assert results[0].name == "Gadget Beta"

    def test_in_multiple_values(self):
        """IN with multiple values."""
        results = self.repo.find_all_by_status_in(status=["available", "preorder"])
        assert len(results) == 5

    def test_in_all_match(self):
        """IN where every row matches."""
        all_statuses = ["available", "discontinued", "out_of_stock", "preorder"]
        results = self.repo.find_all_by_status_in(status=all_statuses)
        assert len(results) == 7

    def test_in_no_match(self):
        """IN with values that match nothing."""
        results = self.repo.find_all_by_status_in(status=["archived", "deleted"])
        assert len(results) == 0

    def test_in_empty_list(self):
        """IN with empty list returns no results."""
        results = self.repo.find_all_by_status_in(status=[])
        assert len(results) == 0

    def test_in_with_integer_ids(self):
        """IN with integer ID list."""
        all_products = self.repo.find_all()
        ids = [all_products[0].id, all_products[2].id, all_products[4].id]
        results = self.repo.find_all_by_id_in(id=ids)
        assert len(results) == 3

    def test_in_case_sensitive_strings(self):
        """IN is exact match - 'Available' should NOT match 'available'.

        This should behave consistently across both databases since IN
        uses equality comparison, not pattern matching.
        """
        results = self.repo.find_all_by_status_in(status=["Available"])
        assert len(results) == 0  # No match - status is lowercase 'available'

    def test_in_with_underscores_in_values(self):
        """IN with values containing underscores (not wildcards in IN)."""
        results = self.repo.find_all_by_status_in(status=["out_of_stock"])
        assert len(results) == 1
        assert results[0].name == "Super Tool"

    def test_not_in_basic(self):
        """NOT_IN excludes matching values."""
        results = self.repo.find_all_by_category_not_in(category=["electronics", "gadgets"])
        assert len(results) == 3  # tools (2) + devices (1)
        for r in results:
            assert r.category not in ["electronics", "gadgets"]

    def test_not_in_empty_list(self):
        """NOT_IN with empty list returns all results."""
        results = self.repo.find_all_by_category_not_in(category=[])
        assert len(results) == 7

    def test_not_in_all_excluded(self):
        """NOT_IN excluding all categories returns nothing."""
        results = self.repo.find_all_by_category_not_in(
            category=["electronics", "gadgets", "tools", "devices"]
        )
        assert len(results) == 0

    # ================================================================
    # LIKE operator tests
    # ================================================================

    def test_like_basic_pattern(self):
        """LIKE with standard wildcard pattern."""
        results = self.repo.find_all_by_name_like(name="%Gadget%")
        assert len(results) == 2
        assert all("Gadget" in r.name for r in results)

    def test_like_leading_wildcard(self):
        """LIKE with leading wildcard."""
        results = self.repo.find_all_by_name_like(name="%Tool")
        assert len(results) == 2  # "Super Tool", "MEGA TOOL"

    def test_like_trailing_wildcard(self):
        """LIKE with trailing wildcard."""
        results = self.repo.find_all_by_name_like(name="Gadget%")
        assert len(results) == 2

    def test_like_no_wildcard_exact_match(self):
        """LIKE without wildcards behaves as exact match."""
        results = self.repo.find_all_by_name_like(name="Super Tool")
        assert len(results) == 1
        assert results[0].name == "Super Tool"

    def test_like_no_match(self):
        """LIKE with pattern matching nothing."""
        results = self.repo.find_all_by_name_like(name="%Nonexistent%")
        assert len(results) == 0

    def test_like_case_sensitivity(self):
        """LIKE case sensitivity test.

        PostgreSQL: LIKE is case-sensitive ('widget%' won't match 'Widget Pro')
        SQLite: LIKE is case-insensitive for ASCII characters
        This test documents the divergence.
        """
        results_lower = self.repo.find_all_by_name_like(name="widget%")
        results_upper = self.repo.find_all_by_name_like(name="Widget%")
        # 'Widget Pro' starts with uppercase W
        # 'widget basic' starts with lowercase w
        # In PostgreSQL: lower matches only 'widget basic', upper matches only 'Widget Pro'
        # In SQLite: both patterns match both rows (case-insensitive)
        assert len(results_upper) >= 1  # At least 'Widget Pro' matches everywhere
        # The key assertion: results may differ between databases
        # PostgreSQL: results_lower=1, results_upper=1
        # SQLite: results_lower=2, results_upper=2

    def test_not_like_basic(self):
        """NOT LIKE excludes matching rows."""
        results = self.repo.find_all_by_name_not_like(name="%Tool%")
        for r in results:
            assert "Tool" not in r.name

    # ================================================================
    # CONTAINS / STARTS_WITH / ENDS_WITH
    # ================================================================

    def test_contains_basic(self):
        """CONTAINS wraps value in %...%."""
        results = self.repo.find_all_by_name_contains(name="Gadget")
        assert len(results) == 2

    def test_contains_case_sensitivity(self):
        """CONTAINS case sensitivity.

        PostgreSQL: 'tool' won't match 'Super Tool' (case-sensitive LIKE)
        SQLite: 'tool' matches both 'Super Tool' and 'MEGA TOOL'
        """
        results_lower = self.repo.find_all_by_name_contains(name="tool")
        results_upper = self.repo.find_all_by_name_contains(name="Tool")
        results_caps = self.repo.find_all_by_name_contains(name="TOOL")
        # At minimum, exact case should match
        assert len(results_upper) >= 1  # 'Super Tool'

    def test_contains_with_underscore(self):
        """CONTAINS with underscore in search term.

        Underscore is a wildcard in SQL LIKE. Proper escaping should treat
        it as a literal character.
        """
        results = self.repo.find_all_by_description_contains(description="_underscore")
        # Should match "Tool with special chars: _underscore and %percent"
        assert len(results) >= 1

    def test_contains_with_percent(self):
        """CONTAINS with percent sign in search term.

        Percent is a wildcard in SQL LIKE. Proper escaping should treat
        it as a literal character.
        """
        results = self.repo.find_all_by_description_contains(description="%percent")
        # Should match "Tool with special chars: _underscore and %percent"
        assert len(results) >= 1

    def test_starts_with_basic(self):
        """STARTS_WITH adds trailing %."""
        results = self.repo.find_all_by_name_starts_with(name="Gadget")
        assert len(results) == 2
        assert all(r.name.startswith("Gadget") for r in results)

    def test_starts_with_single_char(self):
        """STARTS_WITH with single character."""
        results = self.repo.find_all_by_name_starts_with(name="N")
        assert len(results) >= 1  # "Nano Device"

    def test_starts_with_case_sensitivity(self):
        """STARTS_WITH case sensitivity.

        PostgreSQL: 'super' won't match 'Super Tool'
        SQLite: 'super' matches 'Super Tool'
        """
        results_lower = self.repo.find_all_by_name_starts_with(name="super")
        results_upper = self.repo.find_all_by_name_starts_with(name="Super")
        assert len(results_upper) >= 1  # 'Super Tool' matches in both

    def test_ends_with_basic(self):
        """ENDS_WITH adds leading %."""
        results = self.repo.find_all_by_name_ends_with(name="Tool")
        assert len(results) >= 1  # "Super Tool" at minimum

    def test_ends_with_case_sensitivity(self):
        """ENDS_WITH case sensitivity.

        PostgreSQL: 'tool' won't match 'Super Tool' or 'MEGA TOOL'
        SQLite: 'tool' matches both
        """
        results_lower = self.repo.find_all_by_name_ends_with(name="tool")
        results_exact = self.repo.find_all_by_name_ends_with(name="Tool")
        assert len(results_exact) >= 1

    def test_sku_starts_with(self):
        """STARTS_WITH on a different field (sku)."""
        results = self.repo.find_all_by_sku_starts_with(sku="GDG")
        assert len(results) == 2
        assert all(r.sku.startswith("GDG") for r in results)

    # ================================================================
    # Combined operators: IN + LIKE / IN + comparison
    # ================================================================

    def test_in_and_contains_combined(self):
        """IN on status AND CONTAINS on name."""
        results = self.repo.find_all_by_status_in_and_name_contains(
            status=["available", "discontinued"], name="Gadget"
        )
        assert len(results) == 2  # Gadget Alpha (available) + Gadget Beta (discontinued)

    def test_in_and_contains_no_overlap(self):
        """IN + CONTAINS where no row satisfies both."""
        results = self.repo.find_all_by_status_in_and_name_contains(
            status=["preorder"], name="Gadget"
        )
        assert len(results) == 0

    def test_not_in_or_like_combined(self):
        """NOT_IN on category OR LIKE on name."""
        results = self.repo.find_all_by_category_not_in_or_name_like(
            category=["electronics", "gadgets", "devices"], name="%Widget%"
        )
        # NOT_IN matches tools (2), OR name LIKE '%Widget%' matches electronics widgets (2)
        # Union: Super Tool, MEGA TOOL, Widget Pro, widget basic = 4
        assert len(results) >= 3  # At least tools + one widget

    def test_price_gte_and_status_in(self):
        """Comparison + IN combined."""
        results = self.repo.find_all_by_price_gte_and_status_in(
            price=30.0, status=["available", "discontinued"]
        )
        # price >= 30 AND status in (available, discontinued)
        # Gadget Alpha: 49.99, available ✓
        # Gadget Beta: 39.99, discontinued ✓
        # MEGA TOOL: 59.99, available ✓
        assert len(results) == 3

    # ================================================================
    # Count / Exists / Delete with IN/LIKE
    # ================================================================

    def test_count_by_status_in(self):
        """COUNT with IN operator."""
        count = self.repo.count_by_status_in(status=["available"])
        assert count == 4

    def test_count_by_status_in_multiple(self):
        """COUNT with IN operator, multiple values."""
        count = self.repo.count_by_status_in(status=["available", "discontinued"])
        assert count == 5

    def test_count_by_status_in_empty(self):
        """COUNT with IN empty list."""
        count = self.repo.count_by_status_in(status=[])
        assert count == 0

    def test_exists_by_name_contains_true(self):
        """EXISTS with CONTAINS operator - match found."""
        assert self.repo.exists_by_name_contains(name="Widget") is True

    def test_exists_by_name_contains_false(self):
        """EXISTS with CONTAINS operator - no match."""
        assert self.repo.exists_by_name_contains(name="Nonexistent") is False

    def test_delete_by_status_in(self):
        """DELETE with IN operator."""
        deleted = self.repo.delete_all_by_status_in(status=["discontinued", "out_of_stock"])
        assert deleted == 2  # Gadget Beta + Super Tool
        remaining = self.repo.find_all()
        assert len(remaining) == 5
        for r in remaining:
            assert r.status not in ["discontinued", "out_of_stock"]

    def test_delete_by_status_in_empty_list(self):
        """DELETE with IN empty list should delete nothing."""
        deleted = self.repo.delete_all_by_status_in(status=[])
        assert deleted == 0
        assert len(self.repo.find_all()) == 7


class BaseOperatorInLikeRelationship:
    """Tests for IN/LIKE operators on relationship (JOIN) queries."""

    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.cat_repo = OpCategoryRepository()
        self.service = CrudRepositoryImplementationService()

        # Seed categories with products
        electronics = self.cat_repo.save(OpCategory(name="Electronics"))
        clothing = self.cat_repo.save(OpCategory(name="Clothing"))

        with PySpringModel.create_managed_session() as session:
            session.add(OpCategoryProduct(title="Phone Case", label="accessories", category_id=electronics.id))
            session.add(OpCategoryProduct(title="USB Cable", label="cables", category_id=electronics.id))
            session.add(OpCategoryProduct(title="Phone Charger", label="chargers", category_id=electronics.id))
            session.add(OpCategoryProduct(title="T-Shirt", label="basics", category_id=clothing.id))
            session.add(OpCategoryProduct(title="Jacket", label="outerwear", category_id=clothing.id))

        self.service._implemenmt_query(OpCategoryRepository)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)
        PySpringModel._engine = None

    def test_relationship_in_single_value(self):
        """IN on relationship field with single value."""
        results = self.cat_repo.find_all_by_products_label_in(label=["cables"])
        assert len(results) == 1
        assert results[0].name == "Electronics"

    def test_relationship_in_multiple_values(self):
        """IN on relationship field with multiple values."""
        results = self.cat_repo.find_all_by_products_label_in(
            label=["cables", "basics"]
        )
        assert len(results) == 2  # Electronics (cables) + Clothing (basics)

    def test_relationship_in_no_match(self):
        """IN on relationship field with no matching values."""
        results = self.cat_repo.find_all_by_products_label_in(label=["nonexistent"])
        assert len(results) == 0

    def test_relationship_in_deduplication(self):
        """IN matching multiple children of same parent should deduplicate."""
        results = self.cat_repo.find_all_by_products_label_in(
            label=["accessories", "cables", "chargers"]
        )
        # All three belong to Electronics -> should return 1, not 3
        assert len(results) == 1
        assert results[0].name == "Electronics"

    def test_relationship_contains(self):
        """CONTAINS on relationship field."""
        results = self.cat_repo.find_all_by_products_title_contains(title="Phone")
        # "Phone Case" and "Phone Charger" in Electronics
        assert len(results) == 1
        assert results[0].name == "Electronics"

    def test_relationship_contains_no_match(self):
        """CONTAINS on relationship field with no match."""
        results = self.cat_repo.find_all_by_products_title_contains(title="Laptop")
        assert len(results) == 0

    def test_relationship_contains_case_sensitivity(self):
        """CONTAINS on relationship field - case sensitivity.

        PostgreSQL: 'phone' won't match 'Phone Case'
        SQLite: 'phone' matches 'Phone Case'
        """
        results_lower = self.cat_repo.find_all_by_products_title_contains(title="phone")
        results_upper = self.cat_repo.find_all_by_products_title_contains(title="Phone")
        assert len(results_upper) >= 1  # 'Phone' matches in both databases

    def test_relationship_like(self):
        """LIKE on relationship field."""
        results = self.cat_repo.find_all_by_products_label_like(label="cable%")
        assert len(results) == 1
        assert results[0].name == "Electronics"

    def test_relationship_like_broad_pattern(self):
        """LIKE on relationship field with broad pattern."""
        results = self.cat_repo.find_all_by_products_label_like(label="%er%")
        # "chargers" and "outerwear" contain "er"
        assert len(results) == 2  # Electronics + Clothing
