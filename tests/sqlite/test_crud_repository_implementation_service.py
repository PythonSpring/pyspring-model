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


class TestQuery(BaseQuery):
    pass


class TestCountExistsDeleteExecution(BaseCountExistsDeleteExecution):
    pass


class TestRelationshipQueryImplementation(BaseRelationshipQueryImplementation):
    pass


class TestRelationshipSQLGeneration(BaseRelationshipSQLGeneration):
    pass
