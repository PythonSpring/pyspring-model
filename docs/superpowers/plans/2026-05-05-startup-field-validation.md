# Startup-Time Field Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch CrudRepository field name mismatches (typos, wrong columns) at startup instead of at runtime.

**Architecture:** Two changes in `method_query_builder.py`: (1) narrow `except Exception` to `except NoInspectionAvailable` in introspection helpers, (2) add field validation in `parse_query` that checks resolved fields against actual model columns when `model_type` is provided.

**Tech Stack:** Python, SQLAlchemy, SQLModel, pytest

---

## File Structure

- **Modify:** `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py` — narrow exception handling, add validation logic
- **Modify:** `tests/test_method_query_builder.py` — add tests for validation and exception narrowing

---

### Task 1: Narrow exception handling in `get_relationship_fields`

**Files:**
- Test: `tests/test_method_query_builder.py`
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py:76-83`

- [ ] **Step 1: Write the failing test**

Add this test to the `TestGetRelationshipFields` class in `tests/test_method_query_builder.py`:

```python
def test_get_relationship_fields_still_returns_empty_for_non_model(self):
    """Non-SQLModel class should return empty dict via NoInspectionAvailable, not generic Exception."""
    result = get_relationship_fields(str)
    assert result == {}
```

This test already passes — it's a regression guard to confirm behavior is preserved after we narrow the exception type.

- [ ] **Step 2: Run test to verify it passes (regression baseline)**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestGetRelationshipFields::test_get_relationship_fields_still_returns_empty_for_non_model -v`
Expected: PASS

- [ ] **Step 3: Change `except Exception` to `except NoInspectionAvailable`**

In `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py`, add the import and narrow the exception:

At the top of the file, add this import:
```python
from sqlalchemy.exc import NoInspectionAvailable
```

Then change `get_relationship_fields` (lines 80-83) from:
```python
    try:
        mapper = sa_inspect(model_type)
    except Exception:
        return relationships
```
to:
```python
    try:
        mapper = sa_inspect(model_type)
    except NoInspectionAvailable:
        return relationships
```

- [ ] **Step 4: Run test to verify it still passes**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestGetRelationshipFields -v`
Expected: All PASS (including the existing `test_get_relationship_fields_on_non_model_class` in `TestRelationshipEdgeCases`)

- [ ] **Step 5: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "refactor: narrow get_relationship_fields exception to NoInspectionAvailable"
```

---

### Task 2: Narrow exception handling in `_get_column_names`

**Files:**
- Test: `tests/test_method_query_builder.py`
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py:96-100`

- [ ] **Step 1: Write the failing test**

Add a new test class in `tests/test_method_query_builder.py`. Also import `_get_column_names` in the import block at the top of the file:

```python
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.method_query_builder import (
    _MetodQueryBuilder,
    _Query,
    _FieldReference,
    FieldOperation,
    QueryType,
    get_relationship_fields,
    _get_column_names,
)
```

Then add the test class:

```python
class TestGetColumnNames:
    def test_returns_column_names_for_model(self):
        result = _get_column_names(ParentModel)
        assert "id" in result
        assert "name" in result

    def test_returns_empty_set_for_non_model(self):
        result = _get_column_names(str)
        assert result == set()
```

- [ ] **Step 2: Run tests to verify they pass (regression baseline)**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestGetColumnNames -v`
Expected: PASS

- [ ] **Step 3: Change `except Exception` to `except NoInspectionAvailable`**

In `method_query_builder.py`, change `_get_column_names` (lines 96-100) from:
```python
    try:
        mapper = sa_inspect(model_type)
    except Exception:
        return set()
```
to:
```python
    try:
        mapper = sa_inspect(model_type)
    except NoInspectionAvailable:
        return set()
```

- [ ] **Step 4: Run tests to verify they still pass**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestGetColumnNames -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "refactor: narrow _get_column_names exception to NoInspectionAvailable"
```

---

### Task 3: Add startup validation for direct field names

**Files:**
- Test: `tests/test_method_query_builder.py`
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py:200-245`

- [ ] **Step 1: Write the failing test**

Add a new test class in `tests/test_method_query_builder.py`:

```python
class TestFieldValidation:
    """Tests that parse_query validates field names against model columns at startup."""

    def test_invalid_direct_field_raises_error(self):
        """A typo like 'naem' should raise ValueError with helpful message."""
        builder = _MetodQueryBuilder("find_by_naem")
        with pytest.raises(ValueError, match=r"field 'naem' does not exist on model 'ParentModel'"):
            builder.parse_query(model_type=ParentModel)

    def test_invalid_direct_field_lists_available_columns(self):
        """Error message should include available columns for easy correction."""
        builder = _MetodQueryBuilder("find_by_naem")
        with pytest.raises(ValueError, match=r"Available columns:"):
            builder.parse_query(model_type=ParentModel)

    def test_valid_direct_field_passes(self):
        """Valid field 'name' on ParentModel should not raise."""
        builder = _MetodQueryBuilder("find_by_name")
        query = builder.parse_query(model_type=ParentModel)
        assert "name" in query.required_fields

    def test_invalid_field_with_operation_suffix(self):
        """'find_by_naem_gt' — 'naem' is invalid even with an operation suffix."""
        builder = _MetodQueryBuilder("find_by_naem_gt")
        with pytest.raises(ValueError, match=r"field 'naem' does not exist on model 'ParentModel'"):
            builder.parse_query(model_type=ParentModel)

    def test_no_validation_without_model_type(self):
        """When model_type is None, no validation occurs (backwards compatible)."""
        builder = _MetodQueryBuilder("find_by_nonexistent")
        query = builder.parse_query()  # no model_type
        assert "nonexistent" in query.required_fields

    def test_relationship_name_as_field_raises_error(self):
        """'find_all_by_children' — 'children' is a relationship name, not a column."""
        builder = _MetodQueryBuilder("find_all_by_children")
        with pytest.raises(ValueError, match=r"field 'children' does not exist on model 'ParentModel'"):
            builder.parse_query(model_type=ParentModel)
```

Also update the existing test `test_relationship_name_with_no_target_field_treated_as_direct_column` in the `TestRelationshipEdgeCases` class. Change it from asserting the field is silently accepted to asserting it now raises a `ValueError`:

```python
    def test_relationship_name_with_no_target_field_treated_as_direct_column(self):
        """If token equals relationship name exactly (no remaining field), validation catches it."""
        builder = _MetodQueryBuilder("find_all_by_children")
        with pytest.raises(ValueError, match=r"field 'children' does not exist on model 'ParentModel'"):
            builder.parse_query(model_type=ParentModel)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestFieldValidation -v`
Expected: `test_invalid_direct_field_raises_error`, `test_invalid_direct_field_lists_available_columns`, and `test_invalid_field_with_operation_suffix` FAIL (no ValueError raised). `test_valid_direct_field_passes` and `test_no_validation_without_model_type` PASS.

- [ ] **Step 3: Implement direct field validation in `parse_query`**

In `method_query_builder.py`, add a `_validate_fields` method to the `_MetodQueryBuilder` class and call it at the end of `parse_query`.

Add this method to the `_MetodQueryBuilder` class:

```python
    def _validate_fields(
        self,
        model_type: type,
        direct_columns: set[str],
        required_fields: list[str],
        null_check_fields: list[str],
        field_operations: Dict[str, FieldOperation],
        field_references: Dict[str, _FieldReference],
    ) -> None:
        for field in required_fields:
            if field.startswith("min_") or field.startswith("max_"):
                base = field[4:]
                if base not in field_references and base not in direct_columns:
                    raise ValueError(
                        f"Method '{self.method_name}': field '{base}' does not exist on model "
                        f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                    )
                continue
            if field not in field_references and field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )

        for field in null_check_fields:
            if field not in field_references and field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )
```

Then, in `parse_query`, add this call just before the `return _Query(...)` statement (after line 230, before line 232):

```python
        if model_type is not None and direct_columns:
            self._validate_fields(
                model_type,
                direct_columns,
                required_fields,
                null_check_fields,
                field_operations,
                field_references,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestFieldValidation -v`
Expected: All PASS

- [ ] **Step 5: Run full test file to check for regressions**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "feat: validate direct field names against model columns at startup"
```

---

### Task 4: Add startup validation for relationship field names

**Files:**
- Test: `tests/test_method_query_builder.py`
- Modify: `py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py`

- [ ] **Step 1: Write the failing test**

Add these tests to the `TestFieldValidation` class in `tests/test_method_query_builder.py`:

```python
    def test_invalid_relationship_field_raises_error(self):
        """'find_all_by_children_nonexistent' — 'nonexistent' is not a column on ChildModel."""
        builder = _MetodQueryBuilder("find_all_by_children_nonexistent")
        with pytest.raises(ValueError, match=r"field 'nonexistent' does not exist on related model 'ChildModel'"):
            builder.parse_query(model_type=ParentModel)

    def test_invalid_relationship_field_mentions_relationship_name(self):
        """Error should mention the relationship name for context."""
        builder = _MetodQueryBuilder("find_all_by_children_nonexistent")
        with pytest.raises(ValueError, match=r"via relationship 'children'"):
            builder.parse_query(model_type=ParentModel)

    def test_valid_relationship_field_passes(self):
        """Valid relationship field 'children_status' should not raise."""
        builder = _MetodQueryBuilder("find_all_by_children_status")
        query = builder.parse_query(model_type=ParentModel)
        assert "status" in query.field_references

    def test_invalid_relationship_field_with_operation(self):
        """'find_all_by_children_nonexistent_gt' should raise for invalid target field."""
        builder = _MetodQueryBuilder("find_all_by_children_nonexistent_gt")
        with pytest.raises(ValueError, match=r"field 'nonexistent' does not exist on related model 'ChildModel'"):
            builder.parse_query(model_type=ParentModel)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestFieldValidation::test_invalid_relationship_field_raises_error tests/test_method_query_builder.py::TestFieldValidation::test_invalid_relationship_field_mentions_relationship_name tests/test_method_query_builder.py::TestFieldValidation::test_invalid_relationship_field_with_operation -v`
Expected: FAIL (no ValueError raised for invalid relationship fields)

- [ ] **Step 3: Add relationship field validation to `_validate_fields`**

In `method_query_builder.py`, update the `_validate_fields` method. Add relationship validation for fields that ARE in `field_references`. The full updated method:

```python
    def _validate_fields(
        self,
        model_type: type,
        direct_columns: set[str],
        required_fields: list[str],
        null_check_fields: list[str],
        field_operations: Dict[str, FieldOperation],
        field_references: Dict[str, _FieldReference],
    ) -> None:
        for field in required_fields:
            if field.startswith("min_") or field.startswith("max_"):
                base = field[4:]
                if base in field_references:
                    ref = field_references[base]
                    if ref.related_model is not None:
                        related_columns = _get_column_names(ref.related_model)
                        if related_columns and base not in related_columns:
                            raise ValueError(
                                f"Method '{self.method_name}': field '{base}' does not exist on related model "
                                f"'{ref.related_model.__name__}' (via relationship '{ref.relationship_name}'). "
                                f"Available columns: {sorted(related_columns)}"
                            )
                elif base not in direct_columns:
                    raise ValueError(
                        f"Method '{self.method_name}': field '{base}' does not exist on model "
                        f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                    )
                continue

            if field in field_references:
                ref = field_references[field]
                if ref.related_model is not None:
                    related_columns = _get_column_names(ref.related_model)
                    if related_columns and field not in related_columns:
                        raise ValueError(
                            f"Method '{self.method_name}': field '{field}' does not exist on related model "
                            f"'{ref.related_model.__name__}' (via relationship '{ref.relationship_name}'). "
                            f"Available columns: {sorted(related_columns)}"
                        )
            elif field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )

        for field in null_check_fields:
            if field in field_references:
                ref = field_references[field]
                if ref.related_model is not None:
                    related_columns = _get_column_names(ref.related_model)
                    if related_columns and field not in related_columns:
                        raise ValueError(
                            f"Method '{self.method_name}': field '{field}' does not exist on related model "
                            f"'{ref.related_model.__name__}' (via relationship '{ref.relationship_name}'). "
                            f"Available columns: {sorted(related_columns)}"
                        )
            elif field not in direct_columns:
                raise ValueError(
                    f"Method '{self.method_name}': field '{field}' does not exist on model "
                    f"'{model_type.__name__}'. Available columns: {sorted(direct_columns)}"
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py::TestFieldValidation -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_method_query_builder.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add py_spring_model/py_spring_model_rest/service/curd_repository_implementation_service/method_query_builder.py tests/test_method_query_builder.py
git commit -m "feat: validate relationship field names against related model columns at startup"
```

---

### Task 5: Run full test suite and verify no regressions

**Files:**
- No files to modify

- [ ] **Step 1: Run the full test suite**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/ -v --ignore=tests/test_e2e_py_spring_model_provider.py`
Expected: All PASS

- [ ] **Step 2: Run the relationship integration tests specifically**

Run: `cd /Users/william_w_chen/Desktop/pyspring-monorepo/pyspring-model && python -m pytest tests/test_relationship_query_integration.py -v`
Expected: All PASS

- [ ] **Step 3: If any tests fail, fix them before proceeding**

Investigate failures — they likely indicate a valid query method that the new validation is incorrectly rejecting. Adjust validation logic if needed (e.g., the `children` token in `test_relationship_name_with_no_target_field_treated_as_direct_column` is not a real column — this should still parse without validation error since it was never validated before when `model_type` was `None` in those tests; check if that specific test passes `model_type`).
