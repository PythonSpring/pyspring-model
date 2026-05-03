import pytest
from py_spring_model.core.propagation import (
    Propagation,
    TransactionRequiredError,
    ExistingTransactionError,
)


class TestPropagation:
    def test_all_modes_exist(self):
        assert Propagation.REQUIRED.value == "REQUIRED"
        assert Propagation.REQUIRES_NEW.value == "REQUIRES_NEW"
        assert Propagation.SUPPORTS.value == "SUPPORTS"
        assert Propagation.MANDATORY.value == "MANDATORY"
        assert Propagation.NOT_SUPPORTED.value == "NOT_SUPPORTED"
        assert Propagation.NEVER.value == "NEVER"
        assert Propagation.NESTED.value == "NESTED"

    def test_propagation_has_exactly_seven_members(self):
        assert len(Propagation) == 7

    def test_transaction_required_error_is_exception(self):
        with pytest.raises(TransactionRequiredError):
            raise TransactionRequiredError("no active transaction")

    def test_existing_transaction_error_is_exception(self):
        with pytest.raises(ExistingTransactionError):
            raise ExistingTransactionError("transaction already exists")
