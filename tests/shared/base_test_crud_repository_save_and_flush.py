import pytest
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from py_spring_model import PySpringModel
from py_spring_model.core.session_context_holder import SessionContextHolder, Transactional
from py_spring_model.repository.crud_repository import CrudRepository


class SaveFlushUser(PySpringModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)


class SaveFlushUserRepository(CrudRepository[int, SaveFlushUser]):
    ...


class BaseCrudRepositorySaveAndFlush:
    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SessionContextHolder.clear()
        SQLModel.metadata.drop_all(self.engine)

    @pytest.fixture
    def repo(self):
        return SaveFlushUserRepository()

    # --- _is_new detection ---

    def test_is_new_for_transient_entity(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        assert repo._is_new(user) is True

    def test_is_not_new_after_save(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        saved = repo.save(user)
        assert repo._is_new(saved) is False

    # --- save() behavior ---

    def test_save_new_entity_uses_add(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        repo.save(user)
        found = repo.find_by_id(1)
        assert found is not None
        assert found.name == "Alice"
        assert found.email == "alice@test.com"

    def test_save_existing_entity_updates(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        repo.save(user)
        existing = repo.find_by_id(1)
        assert existing is not None
        existing.name = "Bob"
        existing.email = "bob@test.com"
        repo.save(existing)
        updated = repo.find_by_id(1)
        assert updated is not None
        assert updated.name == "Bob"
        assert updated.email == "bob@test.com"

    def test_save_returns_same_instance_for_new_entity(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        saved = repo.save(user)
        assert saved is user

    def test_save_new_entity_assigns_auto_id(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        saved = repo.save_and_flush(user)
        assert saved.id is not None
        assert saved.id == 1

    # --- save_all() behavior ---

    def test_save_all_new_entities(self, repo: SaveFlushUserRepository):
        users = [
            SaveFlushUser(name="Alice", email="alice@test.com"),
            SaveFlushUser(name="Bob", email="bob@test.com"),
        ]
        result = repo.save_all(users)
        assert len(result) == 2
        all_users = repo.find_all()
        assert len(all_users) == 2

    def test_save_all_mix_of_new_and_existing(self, repo: SaveFlushUserRepository):
        alice = SaveFlushUser(name="Alice", email="alice@test.com")
        repo.save(alice)
        existing = repo.find_by_id(1)
        assert existing is not None
        existing.name = "Alice Updated"
        new_user = SaveFlushUser(name="Bob", email="bob@test.com")
        result = repo.save_all([existing, new_user])
        assert len(result) == 2
        all_users = repo.find_all()
        assert len(all_users) == 2
        updated = repo.find_by_id(1)
        assert updated is not None
        assert updated.name == "Alice Updated"

    # --- save_and_flush() ---

    def test_save_and_flush_persists_immediately(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        repo.save_and_flush(user)
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT name FROM save_flush_user WHERE id = 1")).fetchone()
        assert row is not None
        assert row[0] == "Alice"

    def test_save_and_flush_returns_entity_with_id(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        saved = repo.save_and_flush(user)
        assert saved.id is not None
        assert saved.id >= 1

    def test_save_and_flush_then_query_no_autoflush_error(self, repo: SaveFlushUserRepository):
        @Transactional
        def batch_operation():
            user1 = SaveFlushUser(name="Alice", email="alice@test.com")
            repo.save_and_flush(user1)
            user2 = SaveFlushUser(name="Bob", email="bob@test.com")
            repo.save_and_flush(user2)
            all_users = repo.find_all()
            assert len(all_users) == 2

        batch_operation()

    # --- save_all_and_flush() ---

    def test_save_all_and_flush_persists_all(self, repo: SaveFlushUserRepository):
        users = [
            SaveFlushUser(name="Alice", email="alice@test.com"),
            SaveFlushUser(name="Bob", email="bob@test.com"),
        ]
        repo.save_all_and_flush(users)
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT COUNT(*) FROM save_flush_user")).fetchone()
        assert rows is not None
        assert rows[0] == 2

    # --- flush() ---

    def test_flush_writes_pending_changes(self, repo: SaveFlushUserRepository):
        user = SaveFlushUser(name="Alice", email="alice@test.com")
        repo.save(user)
        repo.flush()
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT name FROM save_flush_user WHERE id = 1")).fetchone()
        assert row is not None
        assert row[0] == "Alice"

    # --- Detached entity merge ---

    def test_find_then_mutate_then_save_in_separate_transactions(self, repo: SaveFlushUserRepository):
        repo.save(SaveFlushUser(name="Alice", email="alice@test.com"))
        existing = repo.find_by_id(1)
        assert existing is not None
        existing.name = "Updated"
        repo.save(existing)
        result = repo.find_by_id(1)
        assert result is not None
        assert result.name == "Updated"

    # --- Autoflush regression ---

    def test_save_then_query_with_unique_constraint(self, repo: SaveFlushUserRepository):
        @Transactional
        def operation_with_query_after_save():
            user = SaveFlushUser(name="Alice", email="alice@test.com")
            repo.save(user)
            result = repo.find_all()
            assert len(result) == 1
            assert result[0].name == "Alice"

        operation_with_query_after_save()

    def test_save_new_then_save_existing_in_same_transaction(self, repo: SaveFlushUserRepository):
        """Reproduces the production pattern: query existing, then loop saving
        new records and updating existing records in the same transaction.
        The save(existing) call must not trigger an autoflush crash from
        pending new-record INSERTs."""
        repo.save_and_flush(SaveFlushUser(name="Seed", email="seed@test.com"))

        @Transactional
        def batch_operation():
            existing = repo.find_all()
            existing_by_email = {u.email: u for u in existing}
            incoming = [
                SaveFlushUser(name="New User", email="new@test.com"),
                SaveFlushUser(name="Seed Updated", email="seed@test.com"),
            ]
            for record in incoming:
                found = existing_by_email.get(record.email)
                if found is None:
                    repo.save(record)
                else:
                    found.name = record.name
                    repo.save(found)
            all_users = repo.find_all()
            assert len(all_users) == 2
            names = {u.name for u in all_users}
            assert "New User" in names
            assert "Seed Updated" in names

        batch_operation()

    def test_save_new_with_conflicting_unique_then_merge_existing_crashes(self, repo: SaveFlushUserRepository):
        """Reproduces the ACTUAL production bug: batch 1 adds a new record via
        save(), then batch 2's save(existing) triggers merge() which autoflushs
        the pending INSERT — crashing on a unique constraint violation.
        save() alone does NOT prevent this. save_and_flush() is required."""
        repo.save_and_flush(SaveFlushUser(name="Seed", email="seed@test.com"))

        @Transactional
        def failing_pattern():
            new_record = SaveFlushUser(name="Conflict", email="seed@test.com")
            repo.save(new_record)
            existing = repo.find_by_id(1)
            assert existing is not None
            existing.name = "Updated"
            repo.save(existing)

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            failing_pattern()

    def test_save_and_flush_prevents_autoflush_crash_across_batches(self, repo: SaveFlushUserRepository):
        """Reproduces the two-batch pattern: batch 1 saves new records,
        batch 2 queries and saves. Using save_and_flush in batch 1 ensures
        no pending INSERTs leak into batch 2's queries."""
        @Transactional
        def two_batch_operation():
            batch1 = [
                SaveFlushUser(name="Alice", email="alice@test.com"),
                SaveFlushUser(name="Bob", email="bob@test.com"),
            ]
            for record in batch1:
                repo.save_and_flush(record)

            batch2 = [
                SaveFlushUser(name="Alice Updated", email="alice@test.com"),
                SaveFlushUser(name="Charlie", email="charlie@test.com"),
            ]
            existing = repo.find_all()
            existing_by_email = {u.email: u for u in existing}
            for record in batch2:
                found = existing_by_email.get(record.email)
                if found is None:
                    repo.save_and_flush(record)
                else:
                    found.name = record.name
                    repo.save(found)

            all_users = repo.find_all()
            assert len(all_users) == 3
            names = {u.name for u in all_users}
            assert "Alice Updated" in names
            assert "Bob" in names
            assert "Charlie" in names

        two_batch_operation()
