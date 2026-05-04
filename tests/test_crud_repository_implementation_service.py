

from typing import Optional

from loguru import logger
from pydantic import BaseModel
import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from py_spring_model import PySpringModel, Field, Relationship, CrudRepository, Query
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
    @Query("SELECT * FROM user WHERE name = :name")
    def query_uery_by_name(self, name: str) -> User: ...

    @Query("SELECT * FROM user WHERE name = :name")
    def query_user_view_by_name(self, name: str) -> UserView: ...
    

class TestQuery:
    def setup_method(self):
        logger.info("Setting up test environment...")
        self.engine = create_engine("sqlite:///:memory:", echo=True)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        logger.info("Tearing down test environment...")
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

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


class CountExistsDeleteUserRepository(CrudRepository[int, User]):
    def count_by_status(self, status: str) -> int: ...
    def exists_by_name(self, name: str) -> bool: ...
    def delete_by_name(self, name: str) -> int: ...
    def delete_all_by_status(self, status: str) -> int: ...


class TestCountExistsDeleteExecution:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    @pytest.fixture
    def repo(self):
        return CountExistsDeleteUserRepository()

    @pytest.fixture
    def service(self):
        return CrudRepositoryImplementationService()

    def test_count_by_execution(self, repo, service):
        repo.save(User(name="John", email="j@e.com", status="active"))
        repo.save(User(name="Jane", email="ja@e.com", status="active"))
        repo.save(User(name="Bob", email="b@e.com", status="inactive"))
        service._implemenmt_query(repo.__class__)
        assert repo.count_by_status(status="active") == 2
        assert repo.count_by_status(status="inactive") == 1
        assert repo.count_by_status(status="unknown") == 0

    def test_exists_by_execution(self, repo, service):
        repo.save(User(name="John", email="j@e.com"))
        service._implemenmt_query(repo.__class__)
        assert repo.exists_by_name(name="John") is True
        assert repo.exists_by_name(name="Nobody") is False

    def test_delete_by_execution(self, repo, service):
        repo.save(User(name="John", email="j@e.com"))
        repo.save(User(name="Jane", email="ja@e.com"))
        service._implemenmt_query(repo.__class__)
        count = repo.delete_by_name(name="John")
        assert count == 1
        remaining = repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Jane"

    def test_delete_all_by_execution(self, repo, service):
        repo.save(User(name="John", email="j@e.com", status="active"))
        repo.save(User(name="Jane", email="ja@e.com", status="active"))
        repo.save(User(name="Bob", email="b@e.com", status="inactive"))
        service._implemenmt_query(repo.__class__)
        count = repo.delete_all_by_status(status="active")
        assert count == 2
        remaining = repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Bob"


# ---- Relationship query test models ----

class Author(PySpringModel, table=True):
    __tablename__ = "rel_test_author"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    books: list["Book"] = Relationship(back_populates="author")


class Book(PySpringModel, table=True):
    __tablename__ = "rel_test_book"
    id: int = Field(default=None, primary_key=True)
    title: str = ""
    genre: str = ""
    author_id: Optional[int] = Field(default=None, foreign_key="rel_test_author.id")
    author: Optional[Author] = Relationship(back_populates="books")


class AuthorRepository(CrudRepository[int, Author]):
    def find_all_by_books_genre(self, genre: str) -> list[Author]: ...
    def find_by_books_genre(self, genre: str) -> Author: ...
    def find_all_by_books_title_contains(self, title: str) -> list[Author]: ...
    def find_all_by_books_title_starts_with(self, title: str) -> list[Author]: ...
    def find_all_by_books_title_ends_with(self, title: str) -> list[Author]: ...
    def find_all_by_books_genre_in(self, genre: list[str]) -> list[Author]: ...
    def find_all_by_books_genre_ne(self, genre: str) -> list[Author]: ...
    def find_all_by_books_genre_and_name(self, genre: str, name: str) -> list[Author]: ...
    def find_all_by_books_genre_or_name(self, genre: str, name: str) -> list[Author]: ...
    def count_by_books_genre(self, genre: str) -> int: ...
    def exists_by_books_genre(self, genre: str) -> bool: ...
    def delete_all_by_books_genre(self, genre: str) -> int: ...


class BookRepository(CrudRepository[int, Book]):
    def find_all_by_author_name(self, name: str) -> list[Book]: ...
    def find_all_by_author_name_and_genre(self, name: str, genre: str) -> list[Book]: ...


class TestRelationshipQueryImplementation:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def _seed_data(self):
        """Seed test data: Alice has 2 sci-fi books, Bob has 1 fantasy book."""
        self.author_repo = AuthorRepository()
        self.book_repo = BookRepository()
        self.service = CrudRepositoryImplementationService()

        alice = Author(name="Alice")
        bob = Author(name="Bob")
        self.author_repo.save(alice)
        self.author_repo.save(bob)
        self.alice_id = alice.id
        self.bob_id = bob.id

        session = SessionContextHolder.get_or_create_session()
        session.add(Book(title="Sci-fi Book", genre="sci-fi", author_id=alice.id))
        session.add(Book(title="Another Sci-fi", genre="sci-fi", author_id=alice.id))
        session.add(Book(title="Fantasy Book", genre="fantasy", author_id=bob.id))
        session.commit()

        self.service._implemenmt_query(AuthorRepository)
        self.service._implemenmt_query(BookRepository)

    # --- Basic relationship SELECT ---

    def test_relationship_query_returns_correct_results(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre(genre="sci-fi")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_find_all_deduplicates_with_multiple_matching_children(self):
        """Alice has 2 sci-fi books; result should still be 1 author."""
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre(genre="sci-fi")
        assert len(results) == 1

    def test_find_all_no_match_returns_empty(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre(genre="horror")
        assert len(results) == 0

    def test_find_all_returns_all_when_all_match(self):
        """Both authors have books with some genre — verify both returned."""
        self._seed_data()
        # Add a sci-fi book for Bob too
        session = SessionContextHolder.get_or_create_session()
        session.add(Book(title="Bob Sci-fi", genre="sci-fi", author_id=self.bob_id))
        session.commit()
        results = self.author_repo.find_all_by_books_genre(genre="sci-fi")
        assert len(results) == 2
        names = sorted(r.name for r in results)
        assert names == ["Alice", "Bob"]

    def test_find_by_single_result_with_relationship(self):
        self._seed_data()
        result = self.author_repo.find_by_books_genre(genre="fantasy")
        assert result is not None
        assert result.name == "Bob"

    # --- Operation suffixes on relationship fields ---

    def test_contains_on_relationship_field(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_title_contains(title="Sci-fi")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_starts_with_on_relationship_field(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_title_starts_with(title="Fantasy")
        assert len(results) == 1
        assert results[0].name == "Bob"

    def test_ends_with_on_relationship_field(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_title_ends_with(title="Book")
        # "Sci-fi Book" and "Fantasy Book" end with "Book" -> both authors
        assert len(results) == 2

    def test_in_on_relationship_field(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_in(genre=["sci-fi", "fantasy"])
        assert len(results) == 2
        names = sorted(r.name for r in results)
        assert names == ["Alice", "Bob"]

    def test_in_on_relationship_field_single_value(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_in(genre=["fantasy"])
        assert len(results) == 1
        assert results[0].name == "Bob"

    def test_ne_on_relationship_field(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_ne(genre="sci-fi")
        # Only Bob's fantasy book has genre != "sci-fi"
        assert len(results) == 1
        assert results[0].name == "Bob"

    # --- Mixed: relationship + direct column ---

    def test_mixed_relationship_and_direct_column_with_and(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_and_name(genre="sci-fi", name="Alice")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_mixed_relationship_and_direct_column_no_match(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_and_name(genre="sci-fi", name="Bob")
        assert len(results) == 0

    def test_mixed_relationship_and_direct_column_with_or(self):
        self._seed_data()
        results = self.author_repo.find_all_by_books_genre_or_name(genre="sci-fi", name="Bob")
        # Alice matches genre, Bob matches name -> both
        assert len(results) == 2

    # --- Reverse direction: child filtered by parent ---

    def test_reverse_direction_child_by_parent(self):
        self._seed_data()
        results = self.book_repo.find_all_by_author_name(name="Alice")
        assert len(results) == 2
        assert all(b.author_id == self.alice_id for b in results)

    def test_reverse_direction_no_match(self):
        self._seed_data()
        results = self.book_repo.find_all_by_author_name(name="Nobody")
        assert len(results) == 0

    def test_reverse_mixed_relationship_and_direct(self):
        self._seed_data()
        results = self.book_repo.find_all_by_author_name_and_genre(name="Alice", genre="sci-fi")
        assert len(results) == 2

    def test_reverse_mixed_no_match(self):
        self._seed_data()
        results = self.book_repo.find_all_by_author_name_and_genre(name="Alice", genre="fantasy")
        assert len(results) == 0

    # --- COUNT with relationship ---

    def test_count_with_relationship(self):
        self._seed_data()
        count = self.author_repo.count_by_books_genre(genre="sci-fi")
        assert count == 1  # 1 distinct author, not 2 books

    def test_count_with_relationship_no_match(self):
        self._seed_data()
        count = self.author_repo.count_by_books_genre(genre="horror")
        assert count == 0

    def test_count_deduplicates(self):
        """Alice has 2 sci-fi books — count should still be 1."""
        self._seed_data()
        count = self.author_repo.count_by_books_genre(genre="sci-fi")
        assert count == 1

    # --- EXISTS with relationship ---

    def test_exists_with_relationship_true(self):
        self._seed_data()
        assert self.author_repo.exists_by_books_genre(genre="sci-fi") is True

    def test_exists_with_relationship_false(self):
        self._seed_data()
        assert self.author_repo.exists_by_books_genre(genre="horror") is False

    # --- DELETE with relationship ---

    def test_delete_with_relationship(self):
        self._seed_data()
        count = self.author_repo.delete_all_by_books_genre(genre="fantasy")
        assert count == 1  # Bob deleted
        remaining = self.author_repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Alice"

    def test_delete_with_relationship_no_match(self):
        self._seed_data()
        count = self.author_repo.delete_all_by_books_genre(genre="horror")
        assert count == 0
        assert len(self.author_repo.find_all()) == 2

    def test_delete_with_relationship_deduplicates(self):
        """Alice has 2 sci-fi books — delete should only delete her once."""
        self._seed_data()
        count = self.author_repo.delete_all_by_books_genre(genre="sci-fi")
        assert count == 1
        remaining = self.author_repo.find_all()
        assert len(remaining) == 1
        assert remaining[0].name == "Bob"


class TestRelationshipSQLGeneration:
    """Verify generated SQL contains JOIN and DISTINCT for relationship queries."""

    def test_sql_contains_join_and_distinct(self):
        service = CrudRepositoryImplementationService()
        parsed_query = _MetodQueryBuilder("find_all_by_books_genre").parse_query(model_type=Author)
        statement = service._get_sql_statement(Author, parsed_query, {"genre": "sci-fi"})
        sql = str(statement).replace("\n", "")
        assert "JOIN" in sql
        assert "DISTINCT" in sql

    def test_sql_no_join_for_direct_column(self):
        service = CrudRepositoryImplementationService()
        parsed_query = _MetodQueryBuilder("find_all_by_name").parse_query(model_type=Author)
        statement = service._get_sql_statement(Author, parsed_query, {"name": "Alice"})
        sql = str(statement).replace("\n", "")
        assert "JOIN" not in sql
        assert "DISTINCT" not in sql

    def test_sql_mixed_has_join(self):
        service = CrudRepositoryImplementationService()
        parsed_query = _MetodQueryBuilder("find_all_by_books_genre_and_name").parse_query(model_type=Author)
        statement = service._get_sql_statement(Author, parsed_query, {"genre": "sci-fi", "name": "Alice"})
        sql = str(statement).replace("\n", "")
        assert "JOIN" in sql
        assert "DISTINCT" in sql
        assert "rel_test_book" in sql
        assert "rel_test_author" in sql

    def test_sql_reverse_direction_has_join(self):
        service = CrudRepositoryImplementationService()
        parsed_query = _MetodQueryBuilder("find_all_by_author_name").parse_query(model_type=Book)
        statement = service._get_sql_statement(Book, parsed_query, {"name": "Alice"})
        sql = str(statement).replace("\n", "")
        assert "JOIN" in sql
        assert "DISTINCT" in sql
        assert "rel_test_author" in sql