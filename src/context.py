import inspect
from collections.abc import Iterable
from types import ModuleType

from common.annotation.common.annotation import has_any_annotation
from common.annotation.common.component_annotation import COMPONENT_ANNOTATIONS
from common.annotation.common.dependency import dependency_spec
from common.annotation.common.discovery import iter_modules
from common.annotation.common.injector import DependencyInjector


class ApplicationContext:
    def __init__(self):
        self.beans: dict[type, object] = {}
        self.component_types: set[type] = set()
        self._creating: set[type] = set()
        self.injector = DependencyInjector(self)

    def register(self, cls: type):
        self.component_types.add(cls)
        if cls not in self.beans:
            if cls in self._creating:
                raise RuntimeError(f"Circular dependency while creating {cls.__name__}")
            self._creating.add(cls)
            try:
                self.beans[cls] = self.injector.create(cls)
            finally:
                self._creating.remove(cls)
        return self.beans[cls]

    def get(self, annotation):
        bean_type, many, qualifier = dependency_spec(annotation)
        if not isinstance(bean_type, type):
            raise TypeError(f"Unsupported dependency type: {bean_type!r}")
        candidates = sorted(
            (
                cls
                for cls in self.component_types | self.beans.keys()
                if issubclass(cls, bean_type) and not inspect.isabstract(cls)
            ),
            key=lambda cls: (cls.__module__, cls.__qualname__),
        )
        if qualifier is not None:
            candidates = [
                cls
                for cls in candidates
                if cls.__dict__.get("__qualifier__", cls.__name__) == qualifier
            ]
        if many:
            return [self.register(cls) for cls in candidates]
        if not candidates:
            if qualifier is not None or inspect.isabstract(bean_type):
                raise LookupError(
                    f"No component found for {bean_type.__name__} (qualifier={qualifier!r})"
                )
            return self.register(bean_type)
        if len(candidates) > 1:
            primary = [
                cls for cls in candidates if cls.__dict__.get("__primary__", False)
            ]
            if qualifier is None and len(primary) == 1:
                candidates = primary
            else:
                names = ", ".join(cls.__name__ for cls in candidates)
                raise LookupError(
                    f"Ambiguous dependency {bean_type.__name__}: {names}. Use @Primary or Qualifier."
                )
        return self.register(candidates[0])


def create_application_context(
    packages: list[str], modules: Iterable[ModuleType] | None = None
) -> ApplicationContext:
    context = ApplicationContext()
    discovered_modules = (
        list(modules) if modules is not None else list(iter_modules(packages))
    )
    annotations = set(COMPONENT_ANNOTATIONS)
    for module in discovered_modules:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == module.__name__ and has_any_annotation(
                cls, annotations
            ):
                context.component_types.add(cls)
    context.component_types = {
        cls for cls in context.component_types if not inspect.isabstract(cls)
    }
    for cls in sorted(
        context.component_types, key=lambda cls: (cls.__module__, cls.__qualname__)
    ):
        context.register(cls)
    return context
