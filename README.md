PySpringModel
=============

PySpringModel is a Python module built on top of PySpring that provides a simple and efficient way to interact with SQL databases. It leverages the power of SQLAlchemy and SQLModel to provide a streamlined interface for CRUD operations, and integrates seamlessly with the PySpring framework for Dependency Injection and RESTful API development.

Features
--------

-   SQLModel Integration: PySpringModel uses SQLModel as its core ORM, providing a simple and Pythonic way to define your data models and interact with your database.
-   Automatic CRUD Repository: PySpringModel automatically generates a CRUD repository for each of your SQLModel entities, providing common database operations such as Create, Read, Update, and Delete.
-   Managed Sessions: PySpringModel provides a context manager for database sessions, automatically handling session commit and rollback to ensure data consistency.
-   Dynamic Query Generation: PySpringModel can dynamically generate and execute SQL queries based on method names in your repositories.
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
    email: str = Field()`
```

1.  Define a repository for your model by subclassing `CrudRepository`:

```py
from py_spring_model import CrudRepository

class UserRepository(CrudRepository[int, User]):
    # Implementation will be auto generated based on method name
    def find_by_name(self, name: str) -> User: ... 
    def find_by_name_and_email(self, name: str, email: str) -> User: ...
    
```

1.  Use your repository in your service or controller:

```py
class UserService:
    user_repository: UserRepository
    
    def get_user_by_name(self, name: str) -> User:
        return self.user_repository.find_by_name(name)`
```
1.  Run your application with `PySpringApplication`:

```py
from py_spring_core import PySpringApplication
from py_spring_model.py_spring_model_provider import provide_py_spring_model

PySpringApplication(
    "./app-config.json",
    entity_providers=[provide_py_spring_model()]
).run()
```