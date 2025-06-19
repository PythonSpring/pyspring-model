PySpringModel
=============

PySpringModel is a Python module built on top of PySpring that provides a simple and efficient way to interact with SQL databases. It leverages the power of SQLAlchemy and SQLModel to provide a streamlined interface for CRUD operations, and integrates seamlessly with the PySpring framework for Dependency Injection and RESTful API development.

Features
--------

-   SQLModel Integration: PySpringModel uses SQLModel as its core ORM, providing a simple and Pythonic way to define your data models and interact with your database.
-   Automatic CRUD Repository: PySpringModel automatically generates a CRUD repository for each of your SQLModel entities, providing common database operations such as Create, Read, Update, and Delete.
-   Managed Sessions: PySpringModel provides a context manager for database sessions, automatically handling session commit and rollback to ensure data consistency.
-   Dynamic Query Generation: PySpringModel can dynamically generate and execute SQL queries based on method names in your repositories.
-   Custom SQL Queries: PySpringModel supports custom SQL queries using the `@Query` decorator for complex database operations.
-   RESTful API Integration: PySpringModel integrates with the PySpring framework to automatically generate basic table CRUD APIs for your SQLModel entities.

Installation
------------

`pip install pyspring-model`

Basic Usage
-----------

1.  Define your data models by subclassing `PySpringModel`:

```py
from py_spring_model import PySpringModel
from sqlmodel import Field

class User(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field()
    email: str = Field()
    age: int = Field()
    status: str = Field()
```

2.  Define a repository for your model by subclassing `CrudRepository`:

```py
from py_spring_model import CrudRepository, Query
from typing import Optional, List

class UserRepository(CrudRepository[int, User]):
    # Dynamic method-based queries (auto-implemented)
    def find_by_name(self, name: str) -> Optional[User]: ...
    def find_by_email(self, email: str) -> Optional[User]: ...
    def find_by_name_and_email(self, name: str, email: str) -> Optional[User]: ...
    def find_by_name_or_email(self, name: str, email: str) -> Optional[User]: ...
    def find_all_by_status(self, status: str) -> List[User]: ...
    def find_all_by_age_and_status(self, age: int, status: str) -> List[User]: ...
    
    # Custom SQL queries using @Query decorator
    @Query("SELECT * FROM user WHERE age > {min_age}")
    def find_users_older_than(self, min_age: int) -> List[User]: ...
    
    @Query("SELECT * FROM user WHERE email LIKE '%{domain}%'")
    def find_users_by_email_domain(self, domain: str) -> List[User]: ...
    
    @Query("SELECT * FROM user WHERE age BETWEEN {min_age} AND {max_age}")
    def find_users_by_age_range(self, min_age: int, max_age: int) -> List[User]: ...
```

3.  Use your repository in your service or controller:

```py
class UserService:
    user_repository: UserRepository
    
    def get_user_by_name(self, name: str) -> Optional[User]:
        return self.user_repository.find_by_name(name)
    
    def get_active_users_older_than(self, min_age: int) -> List[User]:
        return self.user_repository.find_users_older_than(min_age)
```

4.  Run your application with `PySpringApplication`:

```py
from py_spring_core import PySpringApplication
from py_spring_model.py_spring_model_provider import provide_py_spring_model

PySpringApplication(
    "./app-config.json",
    entity_providers=[provide_py_spring_model()]
).run()
```

Query Examples
--------------

### Dynamic Method-Based Queries

PySpringModel automatically implements query methods based on their names. The method names follow a specific pattern:

#### Single Result Queries (returns Optional[Model])
```py
# Find by single field
def find_by_name(self, name: str) -> Optional[User]: ...
def get_by_email(self, email: str) -> Optional[User]: ...

# Find by multiple fields with AND condition
def find_by_name_and_email(self, name: str, email: str) -> Optional[User]: ...
def get_by_age_and_status(self, age: int, status: str) -> Optional[User]: ...

# Find by multiple fields with OR condition
def find_by_name_or_email(self, name: str, email: str) -> Optional[User]: ...
def get_by_status_or_age(self, status: str, age: int) -> Optional[User]: ...
```

#### Multiple Result Queries (returns List[Model])
```py
# Find all by single field
def find_all_by_status(self, status: str) -> List[User]: ...
def get_all_by_age(self, age: int) -> List[User]: ...

# Find all by multiple fields with AND condition
def find_all_by_age_and_status(self, age: int, status: str) -> List[User]: ...
def get_all_by_name_and_email(self, name: str, email: str) -> List[User]: ...

# Find all by multiple fields with OR condition
def find_all_by_status_or_age(self, status: str, age: int) -> List[User]: ...
def get_all_by_name_or_email(self, name: str, email: str) -> List[User]: ...
```

### Custom SQL Queries

For complex queries that can't be expressed through method names, use the `@Query` decorator:

#### Basic Custom Queries
```py
@Query("SELECT * FROM user WHERE age > {min_age}")
def find_users_older_than(self, min_age: int) -> List[User]: ...

@Query("SELECT * FROM user WHERE age < {max_age}")
def find_users_younger_than(self, max_age: int) -> List[User]: ...

@Query("SELECT * FROM user WHERE email LIKE '%{domain}%'")
def find_users_by_email_domain(self, domain: str) -> List[User]: ...
```

#### Complex Custom Queries
```py
@Query("SELECT * FROM user WHERE age BETWEEN {min_age} AND {max_age} AND status = {status}")
def find_users_by_age_range_and_status(self, min_age: int, max_age: int, status: str) -> List[User]: ...

@Query("SELECT * FROM user WHERE name LIKE %{name_pattern}% OR email LIKE %{email_pattern}%")
def search_users_by_name_or_email(self, name_pattern: str, email_pattern: str) -> List[User]: ...

@Query("SELECT * FROM user ORDER BY age DESC LIMIT {limit}")
def find_oldest_users(self, limit: int) -> List[User]: ...
```

#### Single Result Custom Queries
```py
@Query("SELECT * FROM user WHERE email = {email} LIMIT 1")
def get_user_by_email(self, email: str) -> Optional[User]: ...

@Query("SELECT * FROM user WHERE name = {name} AND status = {status} LIMIT 1")
def get_user_by_name_and_status(self, name: str, status: str) -> Optional[User]: ...
```

### Built-in CRUD Operations

The `CrudRepository` provides these built-in methods:

```py
# Read operations
user_repository.find_by_id(1)                    # Find by primary key
user_repository.find_all_by_ids([1, 2, 3])      # Find multiple by IDs
user_repository.find_all()                       # Find all records

# Write operations
user_repository.save(user)                       # Save single entity
user_repository.save_all([user1, user2])        # Save multiple entities
user_repository.upsert(user, {"email": "..."})  # Insert or update

# Delete operations
user_repository.delete(user)                     # Delete single entity
user_repository.delete_by_id(1)                 # Delete by ID
user_repository.delete_all([user1, user2])      # Delete multiple entities
user_repository.delete_all_by_ids([1, 2, 3])   # Delete multiple by IDs
```

### Complete Example

Here's a complete example showing all query types:

```py
from py_spring_model import PySpringModel, CrudRepository, Query
from sqlmodel import Field
from typing import Optional, List

# Model definition
class User(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field()
    email: str = Field()
    age: int = Field()
    status: str = Field()

# Repository with all query types
class UserRepository(CrudRepository[int, User]):
    # Dynamic queries
    def find_by_name(self, name: str) -> Optional[User]: ...
    def find_by_email(self, email: str) -> Optional[User]: ...
    def find_by_name_and_status(self, name: str, status: str) -> Optional[User]: ...
    def find_all_by_status(self, status: str) -> List[User]: ...
    def find_all_by_age_and_status(self, age: int, status: str) -> List[User]: ...
    
    # Custom SQL queries
    @Query("SELECT * FROM user WHERE age > {min_age}")
    def find_users_older_than(self, min_age: int) -> List[User]: ...
    
    @Query("SELECT * FROM user WHERE email LIKE '%{domain}%'")
    def find_users_by_email_domain(self, domain: str) -> List[User]: ...
    
    @Query("SELECT * FROM user WHERE age BETWEEN {min_age} AND {max_age}")
    def find_users_by_age_range(self, min_age: int, max_age: int) -> List[User]: ...

# Usage example
class UserService:
    user_repository: UserRepository
    
    def get_user_by_name(self, name: str) -> Optional[User]:
        return self.user_repository.find_by_name(name)
    
    def get_active_users_older_than(self, min_age: int) -> List[User]:
        return self.user_repository.find_users_older_than(min_age)
    
    def get_users_by_email_domain(self, domain: str) -> List[User]:
        return self.user_repository.find_users_by_email_domain(domain)
    
    def get_users_in_age_range(self, min_age: int, max_age: int) -> List[User]:
        return self.user_repository.find_users_by_age_range(min_age, max_age)
```

### Method Naming Conventions

The dynamic query generation follows these naming conventions:

- **Prefixes**: `find_by_`, `get_by_`, `find_all_by_`, `get_all_by_`
- **Single field**: `find_by_name` → `WHERE name = ?`
- **Multiple fields with AND**: `find_by_name_and_email` → `WHERE name = ? AND email = ?`
- **Multiple fields with OR**: `find_by_name_or_email` → `WHERE name = ? OR email = ?`
- **Return types**: 
  - `find_by_*` and `get_by_*` return `Optional[Model]`
  - `find_all_by_*` and `get_all_by_*` return `List[Model]`

### Query Decorator Features

The `@Query` decorator supports:

- **Parameter substitution**: Use `{parameter_name}` in SQL
- **Type safety**: Method parameters must match SQL parameters
- **Return type inference**: Automatically handles `Optional[Model]` and `List[Model]`
- **Error handling**: Validates required parameters and types
- **SQL injection protection**: Parameters are properly escaped