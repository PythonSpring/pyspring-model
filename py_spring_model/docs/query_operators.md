# Field Operations Support in PySpringModel

PySpringModel supports multiple field operations for dynamic query generation, similar to Spring Data JPA. This allows you to find entities using various comparison operators and conditions.

## Supported Field Operations

| Operation | Suffix | Description | Example |
|-----------|--------|-------------|---------|
| `EQUALS` | (default) | Field equals value | `find_by_name` |
| `IN` | `_in` | Field in list of values | `find_by_status_in` |
| `GREATER_THAN` | `_gt` | Field greater than value | `find_by_age_gt` |
| `GREATER_EQUAL` | `_gte` | Field greater than or equal to value | `find_by_age_gte` |
| `LESS_THAN` | `_lt` | Field less than value | `find_by_age_lt` |
| `LESS_EQUAL` | `_lte` | Field less than or equal to value | `find_by_age_lte` |
| `LIKE` | `_like` | Field matches pattern | `find_by_name_like` |
| `NOT_EQUALS` | `_ne` | Field not equals value | `find_by_status_ne` |
| `NOT_IN` | `_not_in` | Field not in list of values | `find_by_category_not_in` |

## Basic Usage

### Method Naming Convention

To use field operations, append the appropriate suffix to your field name in the method signature:

```python
from py_spring_model import PySpringModel, Field, CrudRepository
from typing import List, Optional

class User(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int
    salary: float
    status: str = Field(default="active")
    category: str = Field(default="general")

class UserRepository(CrudRepository[int, User]):
    # IN operations
    def find_all_by_status_in(self, status: List[str]) -> List[User]: ...
    def find_all_by_id_in(self, id: List[int]) -> List[User]: ...
    
    # Comparison operations
    def find_by_age_gt(self, age: int) -> Optional[User]: ...
    def find_all_by_age_gte(self, age: int) -> List[User]: ...
    def find_by_age_lt(self, age: int) -> Optional[User]: ...
    def find_by_age_lte(self, age: int) -> Optional[User]: ...
    
    # Pattern matching
    def find_by_name_like(self, name: str) -> Optional[User]: ...
    
    # Negation operations
    def find_by_status_ne(self, status: str) -> Optional[User]: ...
    def find_by_category_not_in(self, category: List[str]) -> List[User]: ...
```

### Usage Examples

```python
# Create repository instance
user_repo = UserRepository()

# IN operations
active_or_pending_users = user_repo.find_all_by_status_in(
    status=["active", "pending"]
)

users_by_ids = user_repo.find_all_by_id_in(id=[1, 2, 3, 5])

# Comparison operations
adults = user_repo.find_all_by_age_gte(age=18)
young_users = user_repo.find_by_age_lt(age=25)
senior_users = user_repo.find_by_age_gte(age=65)

# Pattern matching
johns = user_repo.find_by_name_like(name="%John%")

# Negation operations
non_active_users = user_repo.find_by_status_ne(status="active")
non_employees = user_repo.find_by_category_not_in(
    category=["employee", "intern"]
)
```

## Combining Operations with Logical Operators

### AND Combinations

```python
class UserRepository(CrudRepository[int, User]):
    # Find users by age > 30 AND status IN list
    def find_by_age_gt_and_status_in(
        self, 
        age: int, 
        status: List[str]
    ) -> Optional[User]: ...
    
    # Find users by salary >= amount AND category IN list
    def find_by_salary_gte_and_category_in(
        self, 
        salary: float, 
        category: List[str]
    ) -> List[User]: ...

# Usage
senior_active_users = user_repo.find_by_age_gt_and_status_in(
    age=30, 
    status=["active", "pending"]
)

high_paid_executives = user_repo.find_by_salary_gte_and_category_in(
    salary=100000.0, 
    category=["executive", "director"]
)
```

### OR Combinations

```python
class UserRepository(CrudRepository[int, User]):
    # Find users by age >= min_age OR category IN list
    def find_by_age_gte_or_category_in(
        self, 
        age: int, 
        category: List[str]
    ) -> Optional[User]: ...
    
    # Find users by status NE value OR salary >= amount
    def find_by_status_ne_or_salary_gte(
        self, 
        status: str, 
        salary: float
    ) -> Optional[User]: ...

# Usage
experienced_or_executives = user_repo.find_by_age_gte_or_category_in(
    age=40, 
    category=["executive", "manager"]
)

non_active_or_high_paid = user_repo.find_by_status_ne_or_salary_gte(
    status="active", 
    salary=80000.0
)
```

## Complex Combinations

```python
class UserRepository(CrudRepository[int, User]):
    # Multiple operations with AND/OR
    def find_by_age_gt_and_status_in_or_category_in(
        self, 
        age: int, 
        status: List[str], 
        category: List[str]
    ) -> Optional[User]: ...

# Usage
target_users = user_repo.find_by_age_gt_and_status_in_or_category_in(
    age=25, 
    status=["active"], 
    category=["premium", "vip"]
)
```

## Edge Cases and Best Practices

### Empty List Handling

When you pass an empty list to IN/NOT IN operations:

```python
# IN with empty list returns no results
users = user_repo.find_all_by_status_in(status=[])
assert len(users) == 0

# NOT IN with empty list returns all results
users = user_repo.find_by_category_not_in(category=[])
assert len(users) == total_user_count
```

### Type Validation

Operations have specific type requirements:

```python
# ✅ Valid - IN operations require collections
users = user_repo.find_all_by_status_in(status=["active", "pending"])
users = user_repo.find_all_by_status_in(status=("active", "pending"))
users = user_repo.find_all_by_status_in(status={"active", "pending"})

# ❌ Invalid - will raise ValueError
users = user_repo.find_all_by_status_in(status="active")  # TypeError

# ✅ Valid - Comparison operations work with appropriate types
users = user_repo.find_by_age_gt(age=25)
users = user_repo.find_by_salary_gte(salary=50000.0)

# ✅ Valid - LIKE operations work with strings
users = user_repo.find_by_name_like(name="%John%")
```

### Method Naming Rules

- Use `find_by_` prefix for methods that return single objects
- Use `find_all_by_` prefix for methods that return lists
- Append operation suffix to field name
- Combine with `_and_` and `_or_` for complex queries
- Field names should match your model attributes exactly

## Generated SQL Examples

The operations generate SQL similar to:

```sql
-- find_all_by_status_in(status=["active", "pending"])
SELECT user.id, user.name, user.email, user.age, user.salary, user.status, user.category 
FROM user 
WHERE user.status IN ('active', 'pending')

-- find_by_age_gt_and_status_in(age=30, status=["active"])
SELECT user.id, user.name, user.email, user.age, user.salary, user.status, user.category 
FROM user 
WHERE user.age > 30 AND user.status IN ('active')

-- find_by_name_like(name="%John%")
SELECT user.id, user.name, user.email, user.age, user.salary, user.status, user.category 
FROM user 
WHERE user.name LIKE '%John%'

-- find_by_salary_gte_or_category_in(salary=80000.0, category=["executive"])
SELECT user.id, user.name, user.email, user.age, user.salary, user.status, user.category 
FROM user 
WHERE user.salary >= 80000.0 OR user.category IN ('executive')
```

## Comparison with Spring Data JPA

| Spring Data JPA | PySpringModel |
|-----------------|---------------|
| `findByAgeGreaterThan(int age)` | `find_by_age_gt(self, age: int)` |
| `findByAgeGreaterThanEqual(int age)` | `find_by_age_gte(self, age: int)` |
| `findByAgeLessThan(int age)` | `find_by_age_lt(self, age: int)` |
| `findByAgeLessThanEqual(int age)` | `find_by_age_lte(self, age: int)` |
| `findByNameLike(String name)` | `find_by_name_like(self, name: str)` |
| `findByStatusNot(String status)` | `find_by_status_ne(self, status: str)` |
| `findByStatusIn(List<String> statuses)` | `find_by_status_in(self, status: List[str])` |
| `findByCategoryNotIn(List<String> categories)` | `find_by_category_not_in(self, category: List[str])` |
| `findByAgeGreaterThanAndStatusIn(int age, List<String> statuses)` | `find_by_age_gt_and_status_in(self, age: int, status: List[str])` |

## Complete Example

```python
from py_spring_model import PySpringModel, Field, CrudRepository
from typing import List, Optional
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# Define the model
class Product(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    category: str
    price: float
    status: str = Field(default="active")
    stock: int = Field(default=0)

# Define the repository
class ProductRepository(CrudRepository[int, Product]):
    # Single field operations
    def find_by_price_gt(self, price: float) -> Optional[Product]: ...
    def find_by_price_gte(self, price: float) -> Optional[Product]: ...
    def find_by_stock_lt(self, stock: int) -> Optional[Product]: ...
    def find_by_name_like(self, name: str) -> Optional[Product]: ...
    def find_by_status_ne(self, status: str) -> Optional[Product]: ...
    def find_by_category_in(self, category: List[str]) -> Optional[Product]: ...
    def find_by_category_not_in(self, category: List[str]) -> Optional[Product]: ...
    
    # Combined operations
    def find_by_price_gte_and_status_in(
        self, 
        price: float, 
        status: List[str]
    ) -> Optional[Product]: ...
    def find_by_stock_lt_or_category_in(
        self, 
        stock: int, 
        category: List[str]
    ) -> Optional[Product]: ...

# Setup database
engine = create_engine("sqlite:///:memory:")
PySpringModel._engine = engine
SQLModel.metadata.create_all(engine)

# Create repository and add data
repo = ProductRepository()
products = [
    Product(name="Laptop", category="electronics", price=999.99, status="active", stock=10),
    Product(name="Phone", category="electronics", price=699.99, status="active", stock=5),
    Product(name="Book", category="books", price=19.99, status="inactive", stock=0),
    Product(name="Tablet", category="electronics", price=399.99, status="pending", stock=2),
]

for product in products:
    repo.save(product)

# Query examples
expensive_products = repo.find_by_price_gt(price=500.0)
print(f"Found {len(expensive_products)} expensive products")

in_stock_products = repo.find_by_stock_gt(stock=0)
print(f"Found {len(in_stock_products)} products in stock")

electronics_in_stock = repo.find_by_category_in_and_stock_gt(
    category=["electronics"], 
    stock=0
)
print(f"Found {len(electronics_in_stock)} electronics products in stock")

# Pattern matching
laptops = repo.find_by_name_like(name="%Laptop%")
print(f"Found {len(laptops)} products with 'Laptop' in name")

# Negation
non_active_products = repo.find_by_status_ne(status="active")
print(f"Found {len(non_active_products)} non-active products")

# Complex combination
target_products = repo.find_by_price_gte_and_status_in(
    price=300.0, 
    status=["active", "pending"]
)
print(f"Found {len(target_products)} active/pending products over $300")
```

This implementation provides comprehensive field operation support similar to Spring Data JPA, with proper handling of edge cases, type validation, and complex query combinations. 