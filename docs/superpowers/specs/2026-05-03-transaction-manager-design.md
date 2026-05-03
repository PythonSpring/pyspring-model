# Transaction Manager Design Spec

## Problem

The `@Transactional` decorator in `session_context_holder.py` has its transaction lifecycle logic (commit, rollback, session creation, depth tracking) hardcoded inline. This makes it impossible to support different transaction propagation modes. Spring Boot's `@Transactional` supports modes like `REQUIRES_NEW`, which is essential for use cases such as audit event logging that must persist even when the calling transaction fails.

## Design Decision: Why Approach A (Strategy Pattern)

Three approaches were evaluated:

1. **Strategy Pattern - TransactionManager with Handler classes (chosen):** Each propagation mode is an isolated handler class behind a `PropagationHandler` protocol. `TransactionManager` is a thin dispatcher. The `@Transactional` decorator delegates entirely to `TransactionManager.execute()`.

2. **Transaction Context Object:** Wraps session + depth + savepoint into a context object managed by a central manager. Rejected because it adds indirection without meaningful benefit over the handler approach.

3. **Decorator Factory with Inline Logic:** Keeps all propagation logic inside the decorator via if/elif branches. Rejected because it violates single responsibility and doesn't scale.

**Rationale for Approach A:** Clean separation of concerns (decorator = glue, manager = dispatch, handler = logic). Each handler is independently testable. Adding a new propagation mode means adding one file. Mirrors Spring's `PlatformTransactionManager` concept.

## Propagation Enum

```python
class Propagation(Enum):
    REQUIRED = "REQUIRED"
    REQUIRES_NEW = "REQUIRES_NEW"
    SUPPORTS = "SUPPORTS"
    MANDATORY = "MANDATORY"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NEVER = "NEVER"
    NESTED = "NESTED"
```

### Behavior Matrix

| Mode | Existing transaction | No existing transaction |
|------|---------------------|------------------------|
| REQUIRED | Join it | Create new |
| REQUIRES_NEW | Suspend it, create new | Create new |
| SUPPORTS | Join it | Run without transaction |
| MANDATORY | Join it | Raise `TransactionRequiredError` |
| NOT_SUPPORTED | Suspend it, run without transaction | Run without transaction |
| NEVER | Raise `ExistingTransactionError` | Run without transaction |
| NESTED | Create savepoint within existing | Create new |

## Architecture

### File Layout

```
py_spring_model/core/
├── model.py                              # unchanged
├── py_spring_session.py                  # unchanged
├── session_context_holder.py             # refactored: stack-based state
├── transaction_manager.py                # new: thin dispatcher
├── propagation.py                        # new: Propagation enum + error types
└── propagation_handlers/
    ├── __init__.py
    ├── propagation_handler.py            # Protocol definition
    ├── required_handler.py
    ├── requires_new_handler.py
    ├── supports_handler.py
    ├── mandatory_handler.py
    ├── not_supported_handler.py
    ├── never_handler.py
    └── nested_handler.py
```

### SessionContextHolder: Stack-based Session Management

**Design decision:** Replace the single `ContextVar[Optional[PySpringSession]]` + single depth counter with a stack of `TransactionState` objects. This enables session suspension for `REQUIRES_NEW` and `NOT_SUPPORTED`.

```python
@dataclass
class TransactionState:
    session: Optional[PySpringSession]
    depth: int
```

**State stored as:**
```python
_session_stack: ClassVar[ContextVar[list[TransactionState]]]
```

**Key operations:**

| Method | Behavior |
|--------|----------|
| `push_state(state)` | Push a new `TransactionState` onto the stack |
| `pop_state() -> TransactionState` | Pop and return the top state, restoring the previous one |
| `current_state() -> Optional[TransactionState]` | Peek at the top of the stack |
| `has_active_transaction()` | `True` if stack is non-empty and top state has session with depth >= 1 |
| `get_or_create_session()` | Reads from `current_state().session`, creates if `None` |
| `clear()` | Closes all sessions in the stack and resets to empty |

**Suspension flow example (REQUIRES_NEW):**
```
1. outer @Transactional(REQUIRED) -> push TransactionState(session=S1, depth=1)
2. inner @Transactional(REQUIRES_NEW) -> push TransactionState(session=S2, depth=1)
   S1 is underneath in the stack, untouched
3. inner completes -> commit/rollback S2, close S2, pop -> S1 restored as current
4. outer completes -> commit/rollback S1, close S1, pop -> stack empty
```

**Dead code removal:** All internal methods from the old `SessionContextHolder` that are no longer needed by the new design will be removed. No backward compatibility shims. Methods like `enter_session()`, `exit_session()`, `is_transaction_managed()`, `get_session_depth()` will be replaced by the stack-based equivalents as needed by the handlers.

### PropagationHandler Protocol

```python
class PropagationHandler(Protocol):
    def handle(self, func: Callable, *args, **kwargs) -> Any: ...
```

Each handler class implements this protocol with its specific transaction semantics.

### Handler Behaviors

**RequiredHandler:**
- If `has_active_transaction()`: increment depth on current state, run func, decrement depth. No commit/rollback (outer manages it).
- If no active transaction: create new session, push `TransactionState(session, depth=1)`, run func, commit on success / rollback on error, close session, pop state.

**RequiresNewHandler:**
- Always create a new session, push a new `TransactionState(session, depth=1)`. Run func. Commit on success / rollback on error. Close session. Pop state. Previous state (if any) is untouched underneath.

**SupportsHandler:**
- If `has_active_transaction()`: run func directly (join, no lifecycle management).
- If no active transaction: run func directly without any session or transaction management.

**MandatoryHandler:**
- If no active transaction: raise `TransactionRequiredError`.
- If `has_active_transaction()`: behave like Required's join path (increment depth, run, decrement).

**NotSupportedHandler:**
- If `has_active_transaction()`: push an empty `TransactionState(session=None, depth=0)` to effectively suspend. Run func. Pop to restore.
- If no active transaction: run func directly.

**NeverHandler:**
- If `has_active_transaction()`: raise `ExistingTransactionError`.
- If no active transaction: run func directly.

**NestedHandler:**
- If `has_active_transaction()`: create a savepoint on the current session via `session.begin_nested()`, which returns a `SessionTransaction` (SQLAlchemy's nested transaction context). The handler manages this `SessionTransaction` locally (not stored in `TransactionState`). Run func. On success: commit via `nested_txn.commit()`. On error: rollback to savepoint via `nested_txn.rollback()` (outer transaction unaffected).
- If no active transaction: behave like Required (create new session, push, run, commit/rollback, pop).

### TransactionManager

Thin dispatcher class:

```python
class TransactionManager:
    _handlers: ClassVar[dict[Propagation, PropagationHandler]] = {
        Propagation.REQUIRED: RequiredHandler(),
        Propagation.REQUIRES_NEW: RequiresNewHandler(),
        Propagation.SUPPORTS: SupportsHandler(),
        Propagation.MANDATORY: MandatoryHandler(),
        Propagation.NOT_SUPPORTED: NotSupportedHandler(),
        Propagation.NEVER: NeverHandler(),
        Propagation.NESTED: NestedHandler(),
    }

    @staticmethod
    def execute(func: Callable, propagation: Propagation, *args, **kwargs) -> Any:
        handler = TransactionManager._handlers[propagation]
        return handler.handle(func, *args, **kwargs)
```

### @Transactional Decorator

Supports both bare and parameterized usage:

```python
def Transactional(
    func: Optional[Callable[P, RT]] = None,
    *,
    propagation: Propagation = Propagation.REQUIRED,
) -> Callable[P, RT]:
    def decorator(fn: Callable[P, RT]) -> Callable[P, RT]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> RT:
            return TransactionManager.execute(fn, propagation, *args, **kwargs)
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
```

**Usage:**
```python
@Transactional
def create_user(): ...

@Transactional(propagation=Propagation.REQUIRES_NEW)
def write_audit_event(event: AuditEvent): ...

@Transactional(propagation=Propagation.SUPPORTS)
def get_user_count(): ...
```

### Error Types

```python
class TransactionRequiredError(Exception):
    """Raised by MANDATORY when no active transaction exists."""

class ExistingTransactionError(Exception):
    """Raised by NEVER when an active transaction exists."""
```

### Public API Exports

Exposed in `py_spring_model/__init__.py`:
- `Transactional` (decorator)
- `Propagation` (enum)
- `SessionContextHolder` (for `get_or_create_session()` in business code)

Internal (not exported):
- `TransactionManager`, all handler classes, `TransactionState`

## Testing Strategy

### Test Structure

```
tests/
├── test_transactional_decorator.py          # existing - update for new API
├── test_session_depth.py                    # existing - update for stack-based state
├── test_session_context_holder.py           # stack push/pop/current_state
├── test_required_handler.py                 # join existing, create new
├── test_requires_new_handler.py             # suspend + new session, restore after
├── test_supports_handler.py                 # join or run without txn
├── test_mandatory_handler.py                # raise if no txn
├── test_not_supported_handler.py            # suspend or run without txn
├── test_never_handler.py                    # raise if txn exists
├── test_nested_handler.py                   # savepoint create/release/rollback
└── test_transaction_manager.py              # dispatch to correct handler
```

### Key Scenarios Per Handler

| Handler | Must test |
|---------|-----------|
| Required | Join existing txn; create new when none; nested depth tracking; rollback on error |
| RequiresNew | New session created even when txn exists; outer session untouched after inner fails; outer session untouched after inner succeeds |
| Supports | Joins when txn exists; runs without session when no txn; no commit/rollback when non-transactional |
| Mandatory | Raises `TransactionRequiredError` when no txn; joins when txn exists |
| NotSupported | Suspends active txn; restores after; runs without session |
| Never | Raises `ExistingTransactionError` when txn exists; runs normally when none |
| Nested | Savepoint created within existing txn; rollback to savepoint on inner error (outer unaffected); creates new txn when none exists |

### Existing Test Updates

- `test_transactional_decorator.py`: All tests should pass since bare `@Transactional` defaults to `REQUIRED` (same behavior as before).
- `test_session_depth.py`: Update to use stack-based API instead of direct depth ContextVar access.
