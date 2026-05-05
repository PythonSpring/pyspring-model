import pytest

from tests.shared.base_test_crud_repository_implementation_service import (
    Author,
    AuthorRepository,
    BaseCountExistsDeleteExecution,
    BaseQuery,
    BaseRelationshipQueryImplementation,
    BaseRelationshipSQLGeneration,
    Book,
    BookRepository,
    CountExistsDeleteUserRepository,
    User,
    UserRepository,
    UserView,
)


@pytest.mark.postgres
class TestQuery(BaseQuery):
    pass


@pytest.mark.postgres
class TestCountExistsDeleteExecution(BaseCountExistsDeleteExecution):
    pass


@pytest.mark.postgres
class TestRelationshipQueryImplementation(BaseRelationshipQueryImplementation):
    pass


@pytest.mark.postgres
class TestRelationshipSQLGeneration(BaseRelationshipSQLGeneration):
    pass
