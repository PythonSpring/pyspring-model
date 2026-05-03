# Design: CrudRepository & Query Layer Coverage Gap Fixes

**Date**: 2026-05-04
**Branch**: `refactor/curd_repository_implementation_service`
**Approach**: Bottom-Up, Layer-by-Layer

## Overview

Full sweep to address coverage gaps across all layers: QueryExecutionService, CrudRepository, MethodQueryBuilder, CrudRepositoryImplementationService, PySpringModelRestService, and PySpringModelRestController. Includes security fixes, feature additions, API consistency improvements, and comprehensive test coverage.

## Breaking Changes

1. **`@Query` template syntax**: `{param}` changes to `:param` (SQLAlchemy bindparam style)
2. **`save_all` return type**: Changes from `bool` to `list[T]`
3. **`update` in PySpringModelRestService**: Now returns `Optional[ModelT]` instead of `None`

---

## Layer 1: QueryExecutionService (`query.py`)

### 1a. SQL Injection Fix (HIGH priority)

**Problem**: `_process_kwargs` at line 84-92 uses string interpolation (`f"'{original_value}'"`) to embed values in SQL. This enables SQL injection through any string parameter.

**Solution**: Switch to SQLAlchemy parameterized queries.

- Change template syntax from `{param}` to `:param`
- Pass parameters to `session.execute(text(sql), params)` instead of formatting into the SQL string
- Remove `_process_kwargs` method entirely
- Update `execute_query` to pass kwargs directly as parameters

**Before**:
```python
sql = query_template.format(**processed_kwargs)
session.execute(text(sql))
```

**After**:
```python
# Template uses :param syntax: "SELECT * FROM users WHERE email = :email"
session.execute(text(query_template), kwargs)
```

### 1b. Optional[T] Return Type (HIGH priority)

**Problem**: When return type is `Optional[T]` and SELECT returns no results, line 67 raises `ValueError` instead of returning `None`.

**Solution**: In the `issubclass(actual_type, BaseModel)` branch, check if the original return type's origin is `Union` and contains `NoneType`. If so, return `None` when result is `None` instead of raising.

### 1c. Scalar Return Types

**Problem**: Return types like `int` (from `COUNT(*)`) fail because `issubclass(int, BaseModel)` is `False`.

**Solution**: Add a branch for scalar types (`int`, `float`, `str`, `bool`):
```python
if actual_type in (int, float, str, bool):
    result = session.execute(text(sql), params).scalar()
    if result is None and is_optional:
        return None
    return cast(RT, result)
```

### 1d. None Return Type

**Problem**: Methods with `-> None` return type (DELETE/UPDATE without RETURNING) fail.

**Solution**: Add a branch that checks if `return_type is type(None)` — execute the query and return `None`.

---

## Layer 2: CrudRepository (`crud_repository.py`)

### 2a. New Methods

**`count() -> int`**:
```python
@Transactional
def count(self) -> int:
    session = SessionContextHolder.get_or_create_session()
    statement = select(func.count()).select_from(self.model_class)
    return session.exec(statement).one()
```

**`count_by(query_by: dict[str, Any]) -> int`**:
```python
@Transactional
def count_by(self, query_by: dict[str, Any]) -> int:
    session = SessionContextHolder.get_or_create_session()
    statement = select(func.count()).select_from(self.model_class).filter_by(**query_by)
    return session.exec(statement).one()
```

**`exists_by_id(id: ID) -> bool`**:
```python
@Transactional
def exists_by_id(self, id: ID) -> bool:
    session = SessionContextHolder.get_or_create_session()
    statement = select(func.count()).select_from(self.model_class).where(self.model_class.id == id)
    return session.exec(statement).one() > 0
```

### 2b. Pagination & Sorting on `find_all`

Add optional parameters while maintaining backward compatibility:
```python
@Transactional
def find_all(
    self,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    order_by: Optional[str] = None,
    ascending: bool = True,
) -> list[T]:
    session = SessionContextHolder.get_or_create_session()
    statement = select(self.model_class)
    if order_by is not None:
        column = getattr(self.model_class, order_by)
        statement = statement.order_by(column.asc() if ascending else column.desc())
    if offset is not None:
        statement = statement.offset(offset)
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.exec(statement).all())
```

### 2c. `save_all` Return Consistency

Change return type from `bool` to `list[T]`:
```python
@Transactional
def save_all(self, entities: Iterable[T]) -> list[T]:
    session = SessionContextHolder.get_or_create_session()
    entity_list = list(entities)
    session.add_all(entity_list)
    return entity_list
```

---

## Layer 3: MethodQueryBuilder & CrudRepositoryImplementationService

### 3a. New Query Type Enum

Add a `QueryType` to `_Query` to distinguish execution strategies:
```python
class QueryType(str, Enum):
    SELECT_ONE = "select_one"
    SELECT_MANY = "select_many"
    COUNT = "count"
    EXISTS = "exists"
    DELETE = "delete"
```

### 3b. New Method Prefixes

Add prefix recognition to `_MetodQueryBuilder.parse_query()`:

| Prefix | Pattern | QueryType | Returns |
|--------|---------|-----------|---------|
| `count_by_*` | `r"count_by_(.*)"` | `COUNT` | `int` |
| `exists_by_*` | `r"exists_by_(.*)"` | `EXISTS` | `bool` |
| `delete_by_*` | `r"delete_by_(.*)"` | `DELETE` | `int` |
| `delete_all_by_*` | `r"delete_all_by_(.*)"` | `DELETE` | `int` |

Also update `CrudRepositoryImplementationService._get_additional_methods()` to recognize these new prefixes in addition to the existing `get_by_`, `find_by_`, `get_all_by_`, `find_all_by_`.

### 3c. New Field Operations

Add to `FieldOperation` enum:
```python
BETWEEN = "between"
IS_NULL = "is_null"
IS_NOT_NULL = "is_not_null"
STARTS_WITH = "starts_with"
ENDS_WITH = "ends_with"
CONTAINS = "contains"
NOT_LIKE = "not_like"
```

Add to `_detect_field_operation` suffix map:
```python
"_between": FieldOperation.BETWEEN,
"_is_not_null": FieldOperation.IS_NOT_NULL,  # Check before _is_null
"_is_null": FieldOperation.IS_NULL,
"_starts_with": FieldOperation.STARTS_WITH,
"_ends_with": FieldOperation.ENDS_WITH,
"_contains": FieldOperation.CONTAINS,
"_not_like": FieldOperation.NOT_LIKE,
```

### 3d. Execution Strategy in CrudRepositoryImplementationService

**BETWEEN** handling:
- One field produces two required parameters: `min_<field>` and `max_<field>`
- Example: `find_all_by_age_between` requires `min_age` and `max_age`
- Condition: `column.between(min_value, max_value)`
- The `_MetodQueryBuilder` marks the field as BETWEEN in `field_operations` but does NOT add the field to `required_fields`. Instead, it adds `min_<field>` and `max_<field>` to `required_fields`
- `_create_parameter_field_mapping` needs a special case: when a field has BETWEEN operation, map `min_<field>` and `max_<field>` parameters to the field
- `_build_filter_conditions` needs a special case: for BETWEEN fields, look up both `min_<field>` and `max_<field>` from params

**IS_NULL / IS_NOT_NULL** handling:
- Field does NOT appear in `required_fields` (takes no parameters)
- Condition: `column.is_(None)` / `column.isnot(None)`
- The `_MetodQueryBuilder` adds the field to `field_operations` but NOT to `required_fields`
- `_build_filter_conditions` needs a special case: for IS_NULL/IS_NOT_NULL fields, generate the condition without looking up a parameter value
- These fields are tracked in a separate list (`null_check_fields`) on `_Query` so `_build_filter_conditions` knows to include them

**STARTS_WITH / ENDS_WITH / CONTAINS** handling:
- Takes one parameter, wraps with `%` automatically
- `STARTS_WITH`: `column.like(f"{value}%")`
- `ENDS_WITH`: `column.like(f"%{value}")`
- `CONTAINS`: `column.like(f"%{value}%")`

**NOT_LIKE**: `~column.like(value)`

**COUNT** execution:
```python
statement = select(func.count()).select_from(model_type).where(combined_condition)
return session.exec(statement).scalar()
```

**EXISTS** execution:
```python
statement = select(func.count()).select_from(model_type).where(combined_condition)
return session.exec(statement).scalar() > 0
```

**DELETE** execution:
```python
statement = delete(model_type).where(combined_condition)
result = session.execute(statement)
return result.rowcount
```

### 3e. Deferred (Future Work)

The following modifiers are deferred to a follow-up iteration:
- Ordering: `find_all_by_status_order_by_name_asc`
- Limit/Top: `find_top_3_by_status`
- Distinct: `find_distinct_by_category`

---

## Layer 4: PySpringModelRestService (`py_spring_model_rest_service.py`)

### 4a. Fix `update` Return Value

Change `update()` to return the updated entity:
```python
@Transactional
def update(self, id: ID, model: ModelT) -> Optional[ModelT]:
    session = SessionContextHolder.get_or_create_session()
    model_type = type(model)
    primary_keys = PySpringModel.get_primary_key_columns(model_type)
    optional_model = session.get(model_type, id)
    if optional_model is None:
        return None
    for key, value in model.model_dump().items():
        if key in primary_keys:
            continue
        setattr(optional_model, key, value)
    session.add(optional_model)
    return optional_model  # <-- was missing
```

### 4b. Remove Redundant `session.commit()` in `delete`

The `@Transactional` decorator handles commit. Remove the explicit `session.commit()` at line 68.

### 4c. New Methods

```python
@Transactional
def count(self, model_type: Type[ModelT]) -> int:
    session = SessionContextHolder.get_or_create_session()
    return session.query(model_type).count()

@Transactional
def batch_create(self, models: list[ModelT]) -> list[ModelT]:
    session = SessionContextHolder.get_or_create_session()
    session.add_all(models)
    return models

@Transactional
def batch_delete(self, model_type: Type[ModelT], ids: list[ID]) -> None:
    session = SessionContextHolder.get_or_create_session()
    session.query(model_type).filter(model_type.id.in_(ids)).delete(synchronize_session='fetch')
```

---

## Layer 5: PySpringModelRestController (`py_spring_model_rest_controller.py`)

### 5a. Fix Duplicate POST Route

Remove the orphaned `@self.router.post(f"/{resource_name}")` at line 49. Move `PostBody` definition outside route decorators so it doesn't accidentally register a route.

### 5b. Generic ID Type

Detect the model's primary key type and use the appropriate path parameter type. Approach:
- Inspect the model's `__fields__` or `__annotations__` for the `id` field type
- Use `Union[int, str]` for path parameters (UUID is passed as string, then parsed)
- Add a helper `_parse_id(id_str: str, model: Type[PySpringModel])` that converts string to int or UUID based on the model's ID type

### 5c. New Routes

```python
# Count
@self.router.get(f"/{resource_name}/count")
def count():
    return self.rest_service.count(model)

# Batch create
@self.router.post(f"/{resource_name}/batch")
def batch_create(models: list[dict[str, Any]]):
    model_type = self.rest_service.get_all_models()[resource_name]
    validated = [model_type.model_validate(m) for m in models]
    return self.rest_service.batch_create(validated)

# Batch delete
@self.router.delete(f"/{resource_name}/batch")
def batch_delete(body: BatchDeleteBody):
    return self.rest_service.batch_delete(model, body.ids)
```

---

## Layer 6: Test Coverage

### Extended Test Files

| File | New Tests |
|------|-----------|
| `test_crud_repository.py` | `count`, `count_by`, `exists_by_id`, `find_all` with offset/limit/order_by, `save_all` returning `list[T]`, `find_all_by_ids` with empty list |
| `test_crud_repository_implementation_service.py` | `count_by_*`, `exists_by_*`, `delete_by_*` method binding and execution |
| `test_method_query_builder.py` | BETWEEN, IS_NULL, IS_NOT_NULL, STARTS_WITH, ENDS_WITH, CONTAINS, NOT_LIKE parsing; new prefix parsing |
| `test_field_operations.py` | Integration tests for all new field operations with real DB |

### New Test Files

| File | Coverage |
|------|----------|
| `test_query_execution_service.py` | Parameterized queries (no SQL injection), Optional[T] returning None, scalar return types, None return type, list[T] with modifying queries |
| `test_py_spring_model_rest_service.py` | get, get_all, get_all_by_ids, create, update (returns entity), delete (no redundant commit), count, batch_create, batch_delete |
| `test_py_spring_model_rest_controller.py` | Route registration (no duplicate POST), request/response for all endpoints, int and UUID ID handling, error responses |

---

## Implementation Order

1. QueryExecutionService fixes (SQL injection, return types)
2. CrudRepository extensions (count, exists_by_id, pagination, save_all)
3. MethodQueryBuilder new operations and prefixes
4. CrudRepositoryImplementationService execution strategies
5. PySpringModelRestService fixes and new methods
6. PySpringModelRestController fixes and new routes
7. Fill remaining test gaps

Each step includes its own tests written before or alongside the implementation.
