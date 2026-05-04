# Startup-Time Field Validation for CrudRepository

## Problem

When a `CrudRepository` subclass defines a method like `find_by_naem` (typo) or `find_by_nonexistent_field`, the framework silently accepts it at startup. The error only surfaces at runtime as a cryptic `AttributeError` deep in the query execution stack, making it very difficult to diagnose whether the issue is a typo, wrong column name, or relationship misconfiguration.

Two contributing factors:
1. `get_relationship_fields` and `_get_column_names` use bare `except Exception` blocks that silently swallow genuine errors (mapper misconfiguration, unresolved forward refs), returning empty results instead.
2. `parse_query` never validates that resolved field names actually exist as columns on the model.

## Solution

### Change 1: Narrow exception handling in introspection helpers

**File:** `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py`

In `get_relationship_fields` (lines 80-83) and `_get_column_names` (lines 96-100), replace `except Exception` with `except NoInspectionAvailable` (from `sqlalchemy.exc`).

`NoInspectionAvailable` is the specific error SQLAlchemy raises for non-model types (e.g., `str`). This preserves the existing behavior for non-model types in tests while letting genuine errors (mapper misconfiguration, unresolved forward references, import failures) propagate with their full stack trace.

### Change 2: Add field validation in `parse_query`

**File:** `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py`

After the field resolution loop in `parse_query` (after line 230), when `model_type` is provided and `direct_columns` is non-empty, validate every resolved field:

**Direct fields** (not in `field_references`): verify the field name exists in `direct_columns`. If not, raise `ValueError`:
```
Method 'find_by_naem': field 'naem' does not exist on model 'User'. Available columns: ['age', 'email', 'id', 'name']
```

**Relationship fields** (in `field_references`): verify the target field exists on the related model's columns (via `_get_column_names(ref.related_model)`). If not, raise `ValueError`:
```
Method 'find_all_by_books_genr': field 'genr' does not exist on related model 'Book' (via relationship 'books'). Available columns: ['author_id', 'genre', 'id', 'title']
```

### Validation timing

This validation executes at startup during `_implemenmt_query` in `CrudRepositoryImplementationService`. The application will fail to start if any repository method references a non-existent field, providing immediate feedback.

## Test plan

1. **Direct field validation:** Define a repository method `find_by_nonexistent_field` and verify it raises `ValueError` at startup with the correct error message listing available columns.
2. **Relationship field validation:** Define a repository method `find_all_by_rel_nonexistent` where `rel` is a valid relationship but `nonexistent` is not a column on the related model, and verify it raises `ValueError` with the correct error message.
3. **Valid methods still work:** Verify that existing valid methods (`find_by_name`, `find_all_by_books_genre`, etc.) continue to parse and execute correctly.
4. **Exception narrowing:** Verify that `get_relationship_fields` and `_get_column_names` still return empty results for non-model types (e.g., `str`) but propagate genuine SQLAlchemy errors.

## Files to modify

- `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py` — both changes
- Test files for the above
