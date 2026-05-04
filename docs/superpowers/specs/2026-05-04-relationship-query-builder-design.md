# Relationship Query Builder Design

## Problem

The current `_MetodQueryBuilder` and `CrudRepositoryImplementationService` generate queries that only support filtering on direct columns of a single model. When models have SQLModel `Relationship` fields (with `back_populates`), the query builder cannot generate JOINs to filter a parent entity by attributes of its related entities.

For example, given:

```python
class StatusEntry(PySpringModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: str = ""
    station: str = ""
    shipping_record_id: Optional[UUID] = Field(default=None, foreign_key="shippingrecord.id")
    shipping_record: Optional["ShippingRecord"] = Relationship(back_populates="status_entries")

class ShippingRecord(PySpringModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vendor: str = ""
    status_entries: list[StatusEntry] = Relationship(back_populates="shipping_record")
```

There is no way to define a repository method like `find_all_by_status_entries_status` that auto-generates a JOIN query filtering `ShippingRecord` rows by `StatusEntry.status`.

## Solution

Extend the method name parser to detect relationship traversals by introspecting the model's relationship metadata. When a field token matches a known relationship name as a prefix, the system splits the token into a relationship path and a target column, then generates the appropriate JOIN and filter.

### Separator Convention

Use single underscore `_` (consistent with existing field naming) with smart introspection to resolve ambiguity. The parser checks field tokens against the model's known `Relationship` field names to determine if a token represents a relationship traversal or a direct column.

Resolution algorithm for a token like `status_entries_status`:
1. Collect all `Relationship` field names from the model (e.g., `["status_entries"]`)
2. Sort by length descending (longest match first) to avoid partial prefix collisions
3. For each relationship name, check if the token starts with `{relationship_name}_`
4. If matched, the remainder after `{relationship_name}_` is the target column on the related model
5. If no relationship matches, treat the entire token as a direct column (existing behavior)

## Usage Examples

### Simple relationship filter

```python
class ShippingRecordRepository(CrudRepository[UUID, ShippingRecord]):
    def find_all_by_status_entries_status(self, status: str) -> list[ShippingRecord]: ...
```

Generated SQL:
```sql
SELECT DISTINCT sr.* FROM shippingrecord sr
JOIN statusentry se ON se.shipping_record_id = sr.id
WHERE se.status = :status
```

### Mixed: relationship field + direct column

```python
def find_all_by_status_entries_station_and_vendor(self, station: str, vendor: str) -> list[ShippingRecord]: ...
```

Generated SQL:
```sql
SELECT DISTINCT sr.* FROM shippingrecord sr
JOIN statusentry se ON se.shipping_record_id = sr.id
WHERE se.station = :station AND sr.vendor = :vendor
```

### Operation suffixes on relationship fields

All existing `FieldOperation` suffixes work on relationship fields:

```python
def find_all_by_status_entries_status_contains(self, status: str) -> list[ShippingRecord]: ...
# -> JOIN + WHERE se.status LIKE '%' || :status || '%'

def find_all_by_status_entries_date_gte(self, date: str) -> list[ShippingRecord]: ...
# -> JOIN + WHERE se.date >= :date
```

### All query types supported

```python
def count_by_status_entries_status(self, status: str) -> int: ...
# -> SELECT COUNT(DISTINCT sr.id) FROM shippingrecord sr JOIN statusentry se ... WHERE se.status = :status

def exists_by_status_entries_status(self, status: str) -> bool: ...
# -> SELECT COUNT(DISTINCT sr.id) > 0 FROM shippingrecord sr JOIN statusentry se ... WHERE se.status = :status

def delete_all_by_status_entries_status(self, status: str) -> int: ...
# -> DELETE FROM shippingrecord WHERE id IN (SELECT DISTINCT sr.id FROM shippingrecord sr JOIN statusentry se ... WHERE se.status = :status)
```

### Reverse direction (child filtered by parent)

```python
class StatusEntryRepository(CrudRepository[UUID, StatusEntry]):
    def find_all_by_shipping_record_vendor(self, vendor: str) -> list[StatusEntry]: ...
```

Generated SQL:
```sql
SELECT DISTINCT se.* FROM statusentry se
JOIN shippingrecord sr ON se.shipping_record_id = sr.id
WHERE sr.vendor = :vendor
```

## Architecture

### Data Model Changes

New data class to represent a field that may traverse a relationship:

```python
class _FieldReference(BaseModel):
    field_name: str                           # target column name (e.g., "status")
    relationship_name: Optional[str] = None   # None = direct column, else relationship name (e.g., "status_entries")
    related_model: Optional[Type] = None      # the related model class (e.g., StatusEntry), None for direct columns
```

The `_Query` model is updated to track field references instead of plain field name strings, so downstream code knows which fields require JOINs:

```python
class _Query(BaseModel):
    raw_query_list: list[str]
    is_one_result: bool
    notations: list[ConditionNotation]
    required_fields: list[str]
    field_operations: Dict[str, FieldOperation] = {}
    query_type: QueryType = QueryType.SELECT_ONE
    null_check_fields: list[str] = []
    field_references: Dict[str, _FieldReference] = {}  # NEW: field_name -> reference info
```

### Relationship Introspection

A utility function to extract relationship metadata from a SQLModel class:

```python
def get_relationship_info(model_type: Type[PySpringModel]) -> dict[str, _RelationshipInfo]:
    """
    Introspect a SQLModel class to find all Relationship fields.
    Returns a dict mapping relationship_name -> _RelationshipInfo(target_model, is_list).

    Uses SQLAlchemy's inspect() or SQLModel's __sqlmodel_relationships__
    to resolve the target model class and relationship direction.
    """
```

### Parser Changes (`_MetodQueryBuilder`)

The `parse_query` method is extended to accept an optional `model_type` parameter. The model type is already available in `CrudRepositoryImplementationService._implemenmt_query()` via `repository_type._get_model_id_type_with_class()`, so it is passed through to the parser. When provided, the parser introspects the model's relationships to resolve field tokens:

1. After splitting tokens on `_and_` / `_or_`, for each token:
   - First, strip any operation suffix (e.g., `_gte`, `_contains`) to get the base field
   - Check if the base field matches a known relationship prefix
   - If yes: create a `_FieldReference` with the relationship info
   - If no: treat as a direct column (existing behavior)

2. The `_Query` result includes the `field_references` dict so `CrudRepositoryImplementationService` knows which fields need JOINs.

### Query Building Changes (`CrudRepositoryImplementationService`)

`_build_filter_conditions` is updated to handle relationship fields:

1. Before building conditions, collect all unique relationships that need JOINs from `field_references`
2. For each relationship field:
   - Use `getattr(related_model, target_field)` instead of `getattr(model_type, field)`
   - Track that a JOIN is needed for this relationship
3. Return both the filter conditions AND the set of required joins

The `create_implementation_wrapper` method is updated:
1. When building the `select()` statement, apply `.join()` for each required relationship
2. Apply `.distinct()` when any one-to-many relationship is joined (to avoid duplicate parent rows)
3. For `COUNT` and `EXISTS` query types, use `COUNT(DISTINCT model.id)` instead of `COUNT(*)`
4. For `DELETE` query type with relationship filters, use a subquery: `DELETE FROM model WHERE id IN (SELECT DISTINCT id FROM model JOIN ...)`

### File Changes

| File | Change |
|------|--------|
| `method_query_builder.py` | Add `_FieldReference` model; update `parse_query()` to accept model type and resolve relationship traversals |
| `crud_repository_implementation_service.py` | Update `_build_filter_conditions` to handle joins; update `create_implementation_wrapper` to apply joins and distinct; add relationship introspection utility |

### No new files needed.

## Scope Limitations (v1)

- **Single-hop only**: `status_entries_status` works, but multi-hop like `status_entries_shipping_record_vendor` is out of scope
- **No eager loading control**: this design is about filtering, not controlling loading strategy (lazy vs eager)
- **No aggregation**: "find all where count of status_entries > 5" is not supported
- **No custom join conditions**: joins are derived from the model's `Relationship` / `foreign_key` definitions

## Error Handling

- If a relationship field's target column doesn't exist on the related model, raise `ValueError` with a clear message: `"Field 'xyz' not found on related model 'StatusEntry' (via relationship 'status_entries')"`
- If a relationship name in the token matches but has no valid remaining field name, raise `ValueError`: `"Relationship 'status_entries' found but no target field specified"`
- Ambiguity: if both a direct column and a relationship traversal could match, prefer the direct column (backwards compatibility)

## Testing Strategy

### Unit tests for parser

- Token with known relationship prefix resolves to `_FieldReference` with relationship info
- Token with no relationship match resolves to direct column (existing behavior)
- Operation suffixes work correctly on relationship fields
- Multiple relationship fields + direct fields in one method name
- Error cases: invalid target field on related model, missing field after relationship name

### Integration tests

- `find_all_by_<relationship>_<field>` returns correct results with JOIN
- Mixed queries (relationship + direct column) with AND/OR
- COUNT, EXISTS, DELETE query types with relationship filters
- One-to-many join produces distinct results (no duplicates)
- Reverse direction (child filtered by parent attribute)
- Empty results when no matches
- All `FieldOperation` suffixes work on relationship fields

### Test models

Create test-specific models with known relationships (similar to the ShippingRecord/StatusEntry example) to avoid depending on external model definitions.
