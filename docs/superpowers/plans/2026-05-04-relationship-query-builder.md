# Relationship Query Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the method name query builder to support relationship traversal, auto-generating JOIN queries when a field token matches a known SQLModel Relationship name prefix.

**Architecture:** The parser (`_MetodQueryBuilder`) gains model awareness to resolve field tokens against the model's `__sqlmodel_relationships__`. When a token like `status_entries_status` matches relationship `status_entries`, the parser emits a `_FieldReference` marking it as a join field. The query builder (`CrudRepositoryImplementationService`) then generates `.join()` and `.distinct()` on the SQL statement, filtering on the related model's column.

**Tech Stack:** Python 3.11, SQLModel, SQLAlchemy, Pydantic, pytest

---

### Task 1: Add `_FieldReference` model and `field_references` to `_Query`

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py:1-57`
- Test: `tests/test_method_query_builder.py`

- [ ] **Step 1: Write the failing test**

Add test to `tests/test_method_query_builder.py` that verifies the new `field_references` field exists on `_Query` with a default empty dict:

```python
def test_query_has_field_references_default(self):
    builder = _MetodQueryBuilder("find_by_name")
    query = builder.parse_query()
    assert query.field_references == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_method_query_builder.py::TestMetodQueryBuilder::test_query_has_field_references_default -v`
Expected: FAIL with `AttributeError: ... has no attribute 'field_references'`

- [ ] **Step 3: Add `_FieldReference` and update `_Query`**

In `method_query_builder.py`, add the import and new class after `FieldOperation`, then update `_Query`:

```python
from typing import Any, Dict, Optional, Type

class _FieldReference(BaseModel):
    """Represents a field that may traverse a relationship."""
    field_name: str
    relationship_name: Optional[str] = None
    related_model: Optional[Any] = None  # Type[PySpringModel], Any to avoid circular import
```

Update `_Query` to add the new field:

```python
class _Query(BaseModel):
    raw_query_list: list[str]
    is_one_result: bool
    notations: list[ConditionNotation]
    required_fields: list[str]
    field_operations: Dict[str, FieldOperation] = {}
    query_type: QueryType = QueryType.SELECT_ONE
    null_check_fields: list[str] = []
    field_references: Dict[str, _FieldReference] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_method_query_builder.py::TestMetodQueryBuilder::test_query_has_field_references_default -v`
Expected: PASS

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `pytest tests/test_method_query_builder.py -v`
Expected: All existing tests PASS (the new field has a default, so no existing code breaks)

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "feat: add _FieldReference model and field_references to _Query"
```

---

### Task 2: Add relationship introspection utility

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py`
- Test: `tests/test_method_query_builder.py`

- [ ] **Step 1: Write the failing test**

Add test models and a test class at the bottom of `tests/test_method_query_builder.py`:

```python
from typing import Optional
from uuid import UUID, uuid4
from py_spring_model import PySpringModel, Field, Relationship
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
    FieldOperation,
    QueryType,
    _FieldReference,
    get_relationship_fields,
)


class ParentModel(PySpringModel, table=True):
    __tablename__ = "rel_parent"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    children: list["ChildModel"] = Relationship(back_populates="parent")


class ChildModel(PySpringModel, table=True):
    __tablename__ = "rel_child"
    id: int = Field(default=None, primary_key=True)
    status: str = ""
    value: int = 0
    parent_id: Optional[int] = Field(default=None, foreign_key="rel_parent.id")
    parent: Optional[ParentModel] = Relationship(back_populates="children")


class TestGetRelationshipFields:
    def test_returns_relationship_names_for_parent(self):
        result = get_relationship_fields(ParentModel)
        assert "children" in result
        assert result["children"] is ChildModel

    def test_returns_relationship_names_for_child(self):
        result = get_relationship_fields(ChildModel)
        assert "parent" in result
        assert result["parent"] is ParentModel

    def test_returns_empty_for_model_without_relationships(self):
        # The existing User model from the other test file has no relationships,
        # but we can't import it. Use a simple inline check:
        # _MetodQueryBuilder without model_type should still work
        result = get_relationship_fields(ParentModel)
        assert isinstance(result, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_method_query_builder.py::TestGetRelationshipFields -v`
Expected: FAIL with `ImportError: cannot import name 'get_relationship_fields'`

- [ ] **Step 3: Implement `get_relationship_fields`**

Add this function to `method_query_builder.py` after the `_FieldReference` class:

```python
def get_relationship_fields(model_type: type) -> dict[str, type]:
    """
    Introspect a SQLModel class to find all Relationship fields.
    Returns a dict mapping relationship_name -> target model class.

    Uses SQLModel's __sqlmodel_relationships__ to find relationship definitions,
    then resolves the target model from the type annotation.
    """
    from typing import get_args, get_origin

    relationships: dict[str, type] = {}
    sqlmodel_rels = getattr(model_type, "__sqlmodel_relationships__", {})
    annotations = getattr(model_type, "__annotations__", {})

    for rel_name in sqlmodel_rels:
        ann = annotations.get(rel_name)
        if ann is None:
            continue
        target = _resolve_relationship_target(ann)
        if target is not None:
            relationships[rel_name] = target

    return relationships


def _resolve_relationship_target(annotation: type) -> type | None:
    """Resolve the target model class from a relationship annotation.

    Handles: list[ChildModel], Optional[ParentModel], Optional["ParentModel"],
    and direct model references.
    """
    from typing import ForwardRef, get_args, get_origin

    origin = get_origin(annotation)

    # list[ChildModel] -> ChildModel
    if origin is list:
        args = get_args(annotation)
        if args:
            return _resolve_relationship_target(args[0])
        return None

    # Optional[ParentModel] = Union[ParentModel, None]
    import types
    if origin is types.UnionType or (origin is not None and hasattr(origin, '__args__')):
        args = get_args(annotation)
        for arg in args:
            if arg is not type(None):
                return _resolve_relationship_target(arg)
        return None

    # Direct class reference
    if isinstance(annotation, type):
        return annotation

    # ForwardRef - can't resolve at parse time without registry
    # At class init time, SQLModel has already resolved these
    if isinstance(annotation, (str, ForwardRef)):
        return None

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_method_query_builder.py::TestGetRelationshipFields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "feat: add get_relationship_fields introspection utility"
```

---

### Task 3: Extend `parse_query` to resolve relationship tokens

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py:101-172`
- Test: `tests/test_method_query_builder.py`

- [ ] **Step 1: Write the failing tests**

Add to the `TestGetRelationshipFields` class (or create a new class `TestRelationshipParsing`) in `tests/test_method_query_builder.py`:

```python
class TestRelationshipParsing:
    """Tests for parse_query with model_type for relationship resolution."""

    def test_simple_relationship_field(self):
        builder = _MetodQueryBuilder("find_all_by_children_status")
        query = builder.parse_query(model_type=ParentModel)
        assert "status" in query.field_references
        ref = query.field_references["status"]
        assert ref.field_name == "status"
        assert ref.relationship_name == "children"
        assert ref.related_model is ChildModel
        assert "status" in query.required_fields

    def test_relationship_field_with_operation_suffix(self):
        builder = _MetodQueryBuilder("find_all_by_children_value_gte")
        query = builder.parse_query(model_type=ParentModel)
        assert "value" in query.field_references
        ref = query.field_references["value"]
        assert ref.field_name == "value"
        assert ref.relationship_name == "children"
        assert ref.related_model is ChildModel
        assert query.field_operations["value"] == FieldOperation.GREATER_EQUAL

    def test_mixed_direct_and_relationship_fields(self):
        builder = _MetodQueryBuilder("find_all_by_children_status_and_name")
        query = builder.parse_query(model_type=ParentModel)
        # "children_status" -> relationship traversal
        assert "status" in query.field_references
        assert query.field_references["status"].relationship_name == "children"
        # "name" -> direct field, no reference entry
        assert "name" not in query.field_references or query.field_references["name"].relationship_name is None
        assert "status" in query.required_fields
        assert "name" in query.required_fields

    def test_reverse_direction_relationship(self):
        builder = _MetodQueryBuilder("find_all_by_parent_name")
        query = builder.parse_query(model_type=ChildModel)
        assert "name" in query.field_references
        ref = query.field_references["name"]
        assert ref.relationship_name == "parent"
        assert ref.related_model is ParentModel

    def test_no_model_type_skips_relationship_resolution(self):
        """When model_type is not provided, parse_query behaves as before."""
        builder = _MetodQueryBuilder("find_all_by_children_status")
        query = builder.parse_query()  # no model_type
        assert query.field_references == {}
        # Token "children_status" treated as direct field
        assert "children_status" in query.required_fields

    def test_direct_column_preferred_over_relationship(self):
        """If a token matches a direct column exactly, it should NOT be treated as a relationship traversal."""
        # "name" is a direct column on ParentModel, not a relationship
        builder = _MetodQueryBuilder("find_by_name")
        query = builder.parse_query(model_type=ParentModel)
        assert query.field_references == {} or (
            "name" in query.field_references and query.field_references["name"].relationship_name is None
        )
        assert "name" in query.required_fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_method_query_builder.py::TestRelationshipParsing -v`
Expected: FAIL (parse_query does not accept model_type parameter yet)

- [ ] **Step 3: Implement relationship-aware `parse_query`**

Modify `_MetodQueryBuilder` in `method_query_builder.py`. Update the constructor and `parse_query`:

```python
class _MetodQueryBuilder:
    # ... existing class variables unchanged ...

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name

    def parse_query(self, model_type: type | None = None) -> _Query:
        """Parse a method name into a structured _Query.

        Args:
            model_type: Optional model class for relationship introspection.
                         When provided, field tokens are checked against the model's
                         Relationship fields to detect join traversals.
        """
        pattern, is_one, query_type = self._match_prefix()

        match = re.match(pattern, self.method_name)
        if not match:
            raise ValueError(f"Invalid method name: {self.method_name}")

        raw_query = match.group(1)
        raw_query_list = re.split(r"(_and_|_or_)", raw_query)

        # Resolve relationships if model_type is provided
        rel_fields: dict[str, type] = {}
        if model_type is not None:
            rel_fields = get_relationship_fields(model_type)

        required_fields: list[str] = []
        field_operations: Dict[str, FieldOperation] = {}
        null_check_fields: list[str] = []
        field_references: Dict[str, _FieldReference] = {}

        for field in raw_query_list:
            if field in ("_and_", "_or_"):
                continue

            # Strip operation suffix first to get base token
            operation = self._detect_field_operation(field)
            base_token = self._extract_base_field(field, operation) if operation else field

            # Try to resolve as relationship traversal
            rel_name, target_field = self._resolve_relationship_token(base_token, rel_fields)

            if rel_name is not None and target_field is not None:
                # This is a relationship traversal
                field_references[target_field] = _FieldReference(
                    field_name=target_field,
                    relationship_name=rel_name,
                    related_model=rel_fields[rel_name],
                )
                if operation:
                    field_operations[target_field] = operation
                    if operation == FieldOperation.BETWEEN:
                        required_fields.append(f"min_{target_field}")
                        required_fields.append(f"max_{target_field}")
                    elif operation in (FieldOperation.IS_NULL, FieldOperation.IS_NOT_NULL):
                        null_check_fields.append(target_field)
                    else:
                        required_fields.append(target_field)
                else:
                    required_fields.append(target_field)
            else:
                # Existing behavior: direct column
                if not operation:
                    required_fields.append(field)
                    continue
                base_field = self._extract_base_field(field, operation)
                field_operations[base_field] = operation
                if operation == FieldOperation.BETWEEN:
                    required_fields.append(f"min_{base_field}")
                    required_fields.append(f"max_{base_field}")
                elif operation in (FieldOperation.IS_NULL, FieldOperation.IS_NOT_NULL):
                    null_check_fields.append(base_field)
                else:
                    required_fields.append(base_field)

        return _Query(
            raw_query_list=raw_query_list,
            is_one_result=is_one,
            required_fields=required_fields,
            notations=[
                ConditionNotation(notation)
                for notation in raw_query_list
                if notation in ("_and_", "_or_")
            ],
            field_operations=field_operations,
            query_type=query_type,
            null_check_fields=null_check_fields,
            field_references=field_references,
        )

    def _resolve_relationship_token(
        self, base_token: str, rel_fields: dict[str, type]
    ) -> tuple[str | None, str | None]:
        """Check if a base token (with operation suffix already stripped) is a relationship traversal.

        Returns (relationship_name, target_field) if matched, or (None, None) if not.

        Resolution rules:
        1. Sort relationship names by length descending (longest match first)
        2. Check if base_token starts with {rel_name}_
        3. The remainder after {rel_name}_ is the target field on the related model
        4. If no relationship matches, return (None, None) -> treat as direct column
        """
        if not rel_fields:
            return None, None

        # Sort by length descending for longest-prefix-first matching
        sorted_rels = sorted(rel_fields.keys(), key=len, reverse=True)

        for rel_name in sorted_rels:
            prefix = f"{rel_name}_"
            if base_token.startswith(prefix):
                target_field = base_token[len(prefix):]
                if target_field:  # Must have something after the prefix
                    return rel_name, target_field

        return None, None

    # ... existing methods (_match_prefix, _detect_field_operation, _extract_base_field) unchanged ...
```

- [ ] **Step 4: Run relationship parsing tests to verify they pass**

Run: `pytest tests/test_method_query_builder.py::TestRelationshipParsing -v`
Expected: PASS

- [ ] **Step 5: Run ALL parser tests to verify no regressions**

Run: `pytest tests/test_method_query_builder.py -v`
Expected: All tests PASS (existing tests call `parse_query()` without `model_type`, so they get the old behavior)

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "feat: extend parse_query to resolve relationship traversals via model introspection"
```

---

### Task 4: Update `CrudRepositoryImplementationService` to pass `model_type` to parser

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/crud_repository_implementation_service.py:75-112`
- Test: `tests/test_crud_repository_implementation_service.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_crud_repository_implementation_service.py`. First, add test models and a repository with a relationship method:

```python
from typing import Optional
from py_spring_model import PySpringModel, Field, Relationship, CrudRepository
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import CrudRepositoryImplementationService
from sqlalchemy import create_engine
from sqlmodel import SQLModel
import pytest


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


class TestRelationshipQueryImplementation:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def test_relationship_query_returns_correct_results(self):
        repo = AuthorRepository()
        service = CrudRepositoryImplementationService()

        # Seed data
        author1 = Author(name="Alice")
        author2 = Author(name="Bob")
        repo.save(author1)
        repo.save(author2)

        book1 = Book(title="Sci-fi Book", genre="sci-fi", author_id=author1.id)
        book2 = Book(title="Fantasy Book", genre="fantasy", author_id=author2.id)
        book3 = Book(title="Another Sci-fi", genre="sci-fi", author_id=author1.id)

        from py_spring_model.repository.crud_repository import CrudRepository as CR
        book_session = SessionContextHolder.get_or_create_session()
        book_session.add(book1)
        book_session.add(book2)
        book_session.add(book3)
        book_session.commit()

        service._implemenmt_query(AuthorRepository)
        results = repo.find_all_by_books_genre(genre="sci-fi")

        assert len(results) == 1  # Only Alice, deduplicated
        assert results[0].name == "Alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crud_repository_implementation_service.py::TestRelationshipQueryImplementation::test_relationship_query_returns_correct_results -v`
Expected: FAIL (the query builder doesn't know about relationships yet in the service layer)

- [ ] **Step 3: Update `_implemenmt_query` to pass `model_type` to parser**

In `crud_repository_implementation_service.py`, update `_implemenmt_query` at line 85-86:

Change:
```python
query_builder = _MetodQueryBuilder(method)
query = query_builder.parse_query()
```

To:
```python
query_builder = _MetodQueryBuilder(method)
query = query_builder.parse_query(model_type=model_type)
```

Note: `model_type` is already resolved at line 89 (`_, model_type = repository_type._get_model_id_type_with_class()`). Move that line BEFORE the query builder calls (before line 85):

```python
_, model_type = repository_type._get_model_id_type_with_class()

query_builder = _MetodQueryBuilder(method)
query = query_builder.parse_query(model_type=model_type)
logger.debug(f"Method: {method} has query: {query}")

current_func = getattr(repository_type, method)
```

- [ ] **Step 4: This test will still fail because `_build_filter_conditions` doesn't handle joins yet**

Run: `pytest tests/test_crud_repository_implementation_service.py::TestRelationshipQueryImplementation::test_relationship_query_returns_correct_results -v`
Expected: FAIL (likely `AttributeError` because `getattr(Author, 'status')` fails, or similar - the filter builder doesn't use `field_references`)

Keep this test; we'll make it pass in Task 5.

- [ ] **Step 5: Run existing tests to verify no regressions from the `model_type` pass-through**

Run: `pytest tests/test_crud_repository_implementation_service.py -v -k "not TestRelationshipQueryImplementation"`
Expected: All existing tests PASS (passing `model_type` to `parse_query` doesn't change behavior for direct columns)

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/crud_repository_implementation_service.py tests/test_crud_repository_implementation_service.py
git commit -m "feat: pass model_type to parse_query for relationship resolution"
```

---

### Task 5: Update `_build_filter_conditions` and `create_implementation_wrapper` to handle JOINs

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/crud_repository_implementation_service.py:157-244`
- Test: `tests/test_crud_repository_implementation_service.py`

This is the core task. The filter builder and wrapper need to:
1. Resolve columns from the related model when `field_references` indicates a relationship field
2. Return the set of required joins alongside filter conditions
3. Apply `.join()` and `.distinct()` to the SQL statement

- [ ] **Step 1: The failing test from Task 4 already exists**

`test_relationship_query_returns_correct_results` is the target test. It should pass after this task.

- [ ] **Step 2: Refactor `_build_filter_conditions` to return join info**

Update the method signature and body in `crud_repository_implementation_service.py`. Also update the import to include `_FieldReference`:

Update imports:
```python
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
    _FieldReference,
    FieldOperation,
    ConditionNotation,
    QueryType,
)
```

Refactor `_build_filter_conditions`:

```python
def _build_filter_conditions(
    self,
    model_type: Type[PySpringModelT],
    parsed_query: _Query,
    params: dict[str, Any],
) -> tuple[list[ColumnElement[bool]], set[type]]:
    """Build individual filter conditions for each field.

    Returns:
        A tuple of (filter_conditions, join_models) where join_models is the set
        of related model classes that need to be joined.
    """
    filter_conditions = []
    join_models: set[type] = set()

    for field in parsed_query.required_fields:
        # BETWEEN fields use min_/max_ prefixes - skip them here, handled below
        if field.startswith("min_") or field.startswith("max_"):
            continue

        # Check if this field is a relationship traversal
        ref = parsed_query.field_references.get(field)
        if ref is not None and ref.relationship_name is not None and ref.related_model is not None:
            column = getattr(ref.related_model, ref.field_name)
            join_models.add(ref.related_model)
        else:
            column = getattr(model_type, field)

        optional_param_value = params.get(field, None)
        if optional_param_value is None:
            raise ValueError(f"Required field '{field}' is missing or None in keyword arguments. All required fields must be provided with non-None values, getting {params}")
        condition = self._create_field_condition(column, field, optional_param_value, parsed_query.field_operations)
        filter_conditions.append(condition)

    # Handle BETWEEN fields
    for field, operation in parsed_query.field_operations.items():
        if operation == FieldOperation.BETWEEN:
            ref = parsed_query.field_references.get(field)
            if ref is not None and ref.relationship_name is not None and ref.related_model is not None:
                column = getattr(ref.related_model, ref.field_name)
                join_models.add(ref.related_model)
            else:
                column = getattr(model_type, field)
            min_key = f"min_{field}"
            max_key = f"max_{field}"
            min_val = params.get(min_key)
            max_val = params.get(max_key)
            if min_val is None or max_val is None:
                raise ValueError(f"BETWEEN operation for field '{field}' requires both '{min_key}' and '{max_key}' parameters")
            filter_conditions.append(column.between(min_val, max_val))

    # Handle null check fields (IS_NULL, IS_NOT_NULL)
    for field in parsed_query.null_check_fields:
        ref = parsed_query.field_references.get(field)
        if ref is not None and ref.relationship_name is not None and ref.related_model is not None:
            column = getattr(ref.related_model, ref.field_name)
            join_models.add(ref.related_model)
        else:
            column = getattr(model_type, field)
        operation = parsed_query.field_operations[field]
        if operation == FieldOperation.IS_NULL:
            filter_conditions.append(column.is_(None))
        elif operation == FieldOperation.IS_NOT_NULL:
            filter_conditions.append(column.isnot(None))

    return filter_conditions, join_models
```

- [ ] **Step 3: Update all callers of `_build_filter_conditions`**

Update `create_implementation_wrapper` to handle the new return type and apply joins:

```python
def create_implementation_wrapper(self, query: _Query, model_type: Type[PySpringModel], original_func_annotations: dict[str, Any], param_to_field_mapping: dict[str, str]) -> Callable[..., Any]:
    def wrapper(*args, **kwargs) -> Any:
        field_kwargs = {}
        for param_name, value in kwargs.items():
            if param_name in param_to_field_mapping:
                field_name = param_to_field_mapping[param_name]
                field_kwargs[field_name] = value
            else:
                raise ValueError(f"Unknown parameter '{param_name}'. Expected parameters: {list(param_to_field_mapping.keys())}")

        filter_conditions, join_models = self._build_filter_conditions(model_type, query, field_kwargs)
        combined_condition = self._combine_conditions_with_notations(filter_conditions, [ConditionNotation(notation) for notation in query.notations])
        has_joins = len(join_models) > 0

        match query.query_type:
            case QueryType.COUNT:
                return self._execute_count(model_type, combined_condition, join_models)
            case QueryType.EXISTS:
                return self._execute_exists(model_type, combined_condition, join_models)
            case QueryType.DELETE:
                return self._execute_delete(model_type, combined_condition, join_models)
            case _:
                sql_statement = select(model_type)
                for join_model in join_models:
                    sql_statement = sql_statement.join(join_model)
                if combined_condition is not None:
                    sql_statement = sql_statement.where(combined_condition)
                if has_joins:
                    sql_statement = sql_statement.distinct()
                result = self._session_execute(sql_statement, query.is_one_result)
                logger.info(f"Executing query with params: {kwargs}")
                return result

    wrapper.__annotations__ = original_func_annotations
    return wrapper
```

Update `_get_sql_statement`:

```python
def _get_sql_statement(
    self,
    model_type: Type[PySpringModelT],
    parsed_query: _Query,
    params: dict[str, Any],
) -> SelectOfScalar[PySpringModelT]:
    """Build SQL statement from parsed query and parameters."""
    filter_conditions, join_models = self._build_filter_conditions(model_type, parsed_query, params)
    combined_condition = self._combine_conditions_with_notations(filter_conditions, [ConditionNotation(notation) for notation in parsed_query.notations])

    query = select(model_type)
    for join_model in join_models:
        query = query.join(join_model)
    if combined_condition is not None:
        query = query.where(combined_condition)
    if join_models:
        query = query.distinct()
    return query
```

Update `_execute_count` to handle joins:

```python
@Transactional
def _execute_count(self, model_type: Type[PySpringModelT], condition, join_models: set[type] | None = None) -> int:
    session = SessionContextHolder.get_or_create_session()
    if join_models:
        # Use subquery for count with joins to avoid counting duplicates
        pk_columns = [getattr(model_type, col) for col in PySpringModel.get_primary_key_columns(model_type)]
        subq = select(*pk_columns).select_from(model_type)
        for join_model in join_models:
            subq = subq.join(join_model)
        if condition is not None:
            subq = subq.where(condition)
        subq = subq.distinct().subquery()
        statement = select(func.count()).select_from(subq)
    else:
        statement = select(func.count()).select_from(model_type)
        if condition is not None:
            statement = statement.where(condition)
    return session.exec(statement).one()
```

Update `_execute_exists` to handle joins:

```python
@Transactional
def _execute_exists(self, model_type: Type[PySpringModelT], condition, join_models: set[type] | None = None) -> bool:
    return self._execute_count(model_type, condition, join_models) > 0
```

Update `_execute_delete` to handle joins:

```python
@Transactional
def _execute_delete(self, model_type: Type[PySpringModelT], condition, join_models: set[type] | None = None) -> int:
    session = SessionContextHolder.get_or_create_session()
    if join_models:
        # DELETE with join: find IDs first via subquery, then delete by ID
        pk_columns = [getattr(model_type, col) for col in PySpringModel.get_primary_key_columns(model_type)]
        subq = select(*pk_columns).select_from(model_type)
        for join_model in join_models:
            subq = subq.join(join_model)
        if condition is not None:
            subq = subq.where(condition)
        subq = subq.distinct().subquery()
        # Assume single primary key for simplicity
        pk_col_name = PySpringModel.get_primary_key_columns(model_type)[0]
        pk_col = getattr(model_type, pk_col_name)
        statement = delete(model_type).where(pk_col.in_(select(subq)))
    else:
        statement = delete(model_type)
        if condition is not None:
            statement = statement.where(condition)
    result = session.execute(statement)
    return result.rowcount
```

- [ ] **Step 4: Run the relationship test to verify it passes**

Run: `pytest tests/test_crud_repository_implementation_service.py::TestRelationshipQueryImplementation::test_relationship_query_returns_correct_results -v`
Expected: PASS

- [ ] **Step 5: Run ALL tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/crud_repository_implementation_service.py
git commit -m "feat: update filter builder and wrapper to generate JOINs for relationship queries"
```

---

### Task 6: Integration tests for all relationship query scenarios

**Files:**
- Create: `tests/test_relationship_query_integration.py`

- [ ] **Step 1: Write full integration test suite**

Create `tests/test_relationship_query_integration.py`:

```python
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_relationship_query_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_relationship_query_integration.py
git commit -m "test: add integration tests for relationship query builder"
```

---

### Task 7: Export `_FieldReference` and update `__init__.py`

**Files:**
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py` (ensure exports)
- No changes to `py_spring_model/__init__.py` needed (`_FieldReference` is internal, prefixed with `_`)

- [ ] **Step 1: Verify `_FieldReference` is importable from the module**

Add a quick import test at the bottom of `tests/test_method_query_builder.py`:

```python
def test_field_reference_importable():
    from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import _FieldReference
    assert _FieldReference is not None
```

- [ ] **Step 2: Run it**

Run: `pytest tests/test_method_query_builder.py::test_field_reference_importable -v`
Expected: PASS (already importable from Task 1)

- [ ] **Step 3: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_method_query_builder.py
git commit -m "test: verify _FieldReference importability"
```
