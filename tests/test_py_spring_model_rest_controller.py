from sqlalchemy import create_engine
from sqlmodel import SQLModel, Field
from fastapi import APIRouter

from py_spring_model import PySpringModel
from py_spring_model.core.commons import PySpringModelProperties
from py_spring_model.core.session_context_holder import SessionContextHolder
from py_spring_model.py_spring_model_rest.service.py_spring_model_rest_service import PySpringModelRestService
from py_spring_model.py_spring_model_rest.controller.py_spring_model_rest_controller import PySpringModelRestController


class CtrlUser(PySpringModel, table=True):
    __tablename__ = "ctrl_user"
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


def _make_properties(create_crud_routes: bool = False) -> PySpringModelProperties:
    return PySpringModelProperties(
        sqlalchemy_database_uri="sqlite:///:memory:",
        create_crud_routes=create_crud_routes,
    )


class TestPySpringModelRestController:
    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([CtrlUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def _create_controller(self):
        controller = PySpringModelRestController.__new__(PySpringModelRestController)
        controller.rest_service = PySpringModelRestService()
        controller.router = APIRouter()
        controller.properties = _make_properties(create_crud_routes=True)
        controller._register_basic_crud_routes("ctrl_user", CtrlUser)
        return controller

    def test_no_duplicate_post_routes(self):
        """Verify that there is no duplicate POST route for the same resource"""
        controller = self._create_controller()
        post_routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods') and 'POST' in route.methods
            and route.path == "/ctrl_user"
        ]
        # Should only have exactly one POST /ctrl_user route (create)
        assert len(post_routes) == 1

    def test_count_route_registered(self):
        """Verify count route is registered"""
        controller = self._create_controller()
        get_routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods') and 'GET' in route.methods
        ]
        paths = [route.path for route in get_routes]
        assert "/ctrl_user/count" in paths

    def test_batch_create_route_registered(self):
        """Verify batch create route is registered"""
        controller = self._create_controller()
        post_routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods') and 'POST' in route.methods
        ]
        paths = [route.path for route in post_routes]
        assert "/ctrl_user/batch" in paths

    def test_batch_delete_route_registered(self):
        """Verify batch delete route is registered"""
        controller = self._create_controller()
        delete_routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods') and 'DELETE' in route.methods
        ]
        paths = [route.path for route in delete_routes]
        assert "/ctrl_user/batch" in paths

    def test_all_expected_routes_registered(self):
        """Verify all expected routes are registered"""
        controller = self._create_controller()
        all_routes = [
            (route.path, list(route.methods)[0])
            for route in controller.router.routes
            if hasattr(route, 'methods')
        ]
        expected = [
            ("/ctrl_user/count", "GET"),
            ("/ctrl_user/{id}", "GET"),
            ("/ctrl_user/{limit}/{offset}", "GET"),
            ("/ctrl_user/ids", "POST"),
            ("/ctrl_user", "POST"),
            ("/ctrl_user/batch", "POST"),
            ("/ctrl_user/{id}", "PUT"),
            ("/ctrl_user/{id}", "DELETE"),
            ("/ctrl_user/batch", "DELETE"),
        ]
        for path, method in expected:
            assert (path, method) in all_routes, f"Missing route: {method} {path}"


class TestPostConstructConditionalRegistration:
    """Tests for the create_crud_routes property gating route registration."""

    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([CtrlUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def _create_controller_with_properties(self, create_crud_routes: bool) -> PySpringModelRestController:
        controller = PySpringModelRestController.__new__(PySpringModelRestController)
        controller.rest_service = PySpringModelRestService()
        controller.router = APIRouter()
        controller.properties = _make_properties(create_crud_routes=create_crud_routes)
        return controller

    def test_post_construct_registers_routes_when_enabled(self):
        """When create_crud_routes=True, post_construct should register CRUD routes."""
        controller = self._create_controller_with_properties(create_crud_routes=True)
        controller.post_construct()

        routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods')
        ]
        assert len(routes) > 0

    def test_post_construct_skips_routes_when_disabled(self):
        """When create_crud_routes=False, post_construct should not register any routes."""
        controller = self._create_controller_with_properties(create_crud_routes=False)
        controller.post_construct()

        routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods')
        ]
        assert len(routes) == 0

    def test_post_construct_default_property_skips_routes(self):
        """The default value of create_crud_routes is False, so no routes should be registered."""
        controller = PySpringModelRestController.__new__(PySpringModelRestController)
        controller.rest_service = PySpringModelRestService()
        controller.router = APIRouter()
        controller.properties = PySpringModelProperties(
            sqlalchemy_database_uri="sqlite:///:memory:",
        )
        controller.post_construct()

        routes = [
            route for route in controller.router.routes
            if hasattr(route, 'methods')
        ]
        assert len(routes) == 0


class TestRegisterBasicCrudRoutesRouterAssertion:
    """Tests for the router assertion in _register_basic_crud_routes."""

    def setup_method(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        PySpringModel.set_engine(self.engine)
        PySpringModel.set_metadata(SQLModel.metadata)
        PySpringModel.set_models([CtrlUser])
        SessionContextHolder.clear()
        SQLModel.metadata.create_all(self.engine)

    def teardown_method(self):
        SQLModel.metadata.drop_all(self.engine)
        SessionContextHolder.clear()

    def test_register_routes_raises_when_router_is_none(self):
        """_register_basic_crud_routes should raise AssertionError when router is None."""
        controller = PySpringModelRestController.__new__(PySpringModelRestController)
        controller.rest_service = PySpringModelRestService()
        controller.router = None
        controller.properties = _make_properties(create_crud_routes=True)

        import pytest
        with pytest.raises(AssertionError, match="Router must be initialized"):
            controller._register_basic_crud_routes("ctrl_user", CtrlUser)
