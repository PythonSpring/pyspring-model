from py_spring_model.core.propagation_handlers.propagation_handler import PropagationHandler


class TestPropagationHandlerProtocol:
    def test_concrete_class_satisfies_protocol(self):
        class FakeHandler:
            def handle(self, func, *args, **kwargs):
                return func(*args, **kwargs)

        handler: PropagationHandler = FakeHandler()
        result = handler.handle(lambda x: x + 1, 5)
        assert result == 6
