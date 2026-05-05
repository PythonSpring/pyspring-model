"""
Tests for CrudRepositoryImplementationService helper methods and edge cases.
Covers: _cast_plural_to_singular, unknown parameter in wrapper,
_get_additional_methods filtering.
"""

import pytest
from sqlmodel import SQLModel

from py_spring_model import PySpringModel, Field, CrudRepository
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.curd_repository_implementation_service.crud_repository_implementation_service import (
    CrudRepositoryImplementationService,
)


class BaseCastPluralToSingular:
    """Tests for _cast_plural_to_singular edge cases."""

    def setup_method(self):
        self.service = CrudRepositoryImplementationService()

    def test_regular_plural(self):
        assert self.service._cast_plural_to_singular("names") == "name"

    def test_ies_suffix(self):
        assert self.service._cast_plural_to_singular("categories") == "category"

    def test_ses_suffix(self):
        # "addresses" ends with "ses", so the method strips the trailing "es"
        assert self.service._cast_plural_to_singular("addresses") == "address"

    def test_single_char_s(self):
        # Single char 's' should just drop the 's'
        assert self.service._cast_plural_to_singular("ss") == "s"

    def test_statuses(self):
        assert self.service._cast_plural_to_singular("statuses") == "status"


class EdgeCaseModel(PySpringModel, table=True):
    __tablename__ = "edge_case_model"
    id: int = Field(default=None, primary_key=True)
    name: str = ""
    status: str = ""


class EdgeCaseRepo(CrudRepository[int, EdgeCaseModel]):
    def find_by_name(self, name: str) -> EdgeCaseModel: ...

    # Methods that should NOT be picked up by _get_additional_methods
    def custom_logic(self) -> None: ...
    def do_something(self) -> None: ...


class BaseGetAdditionalMethods:
    """Tests for _get_additional_methods filtering."""

    def test_only_recognized_prefixes_are_included(self):
        service = CrudRepositoryImplementationService()
        methods = service._get_additional_methods(EdgeCaseRepo)
        assert "find_by_name" in methods
        assert "custom_logic" not in methods
        assert "do_something" not in methods

    def test_dunder_methods_excluded(self):
        service = CrudRepositoryImplementationService()
        methods = service._get_additional_methods(EdgeCaseRepo)
        for m in methods:
            assert not m.startswith("__")


class WrapperModel(PySpringModel, table=True):
    __tablename__ = "wrapper_model"
    id: int = Field(default=None, primary_key=True)
    name: str = ""


class WrapperRepo(CrudRepository[int, WrapperModel]):
    def find_by_name(self, name: str) -> WrapperModel: ...


class BaseWrapperUnknownParameter:
    """Tests that the generated wrapper rejects unknown parameters."""

    def setup_method(self):
        PySpringModel._engine = self.engine
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

        self.repo = WrapperRepo()
        self.service = CrudRepositoryImplementationService()
        self.service._implemenmt_query(WrapperRepo)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()
        PySpringModel._engine = None

    def test_unknown_parameter_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown parameter"):
            self.repo.find_by_name(unknown_param="value")  # type: ignore
