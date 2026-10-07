import inspect
from typing import Any, get_type_hints


class DependencyInjector:
    def __init__(self, context):
        self.context = context

    def create(self, cls: type) -> Any:
        signature = inspect.signature(cls.__init__)
        type_hints = get_type_hints(cls.__init__)
        dependencies = {}

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue

            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            if parameter.default is not inspect.Parameter.empty:
                continue

            dependency_type = type_hints.get(name, parameter.annotation)

            if dependency_type is inspect.Parameter.empty:
                raise TypeError(f"{cls.__name__}.{name} must have a type annotation")

            dependencies[name] = self.context.get(dependency_type)

        return cls(**dependencies)
