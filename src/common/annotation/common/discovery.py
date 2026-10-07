"""Shared package discovery primitives for annotation integrations."""

import importlib
import pkgutil
from collections.abc import Iterator
from types import ModuleType


def normalize_packages(package_name: str | list[str]) -> list[str]:
    return [package_name] if isinstance(package_name, str) else package_name


def iter_modules(package_name: str | list[str]) -> Iterator[ModuleType]:
    """Yield each requested package and its descendants exactly once."""

    seen: set[str] = set()
    for name in normalize_packages(package_name):
        package = importlib.import_module(name)
        module_names = [package.__name__]
        if hasattr(package, "__path__"):
            module_names.extend(
                module_name
                for _, module_name, _ in pkgutil.walk_packages(
                    package.__path__,
                    package.__name__ + ".",
                )
            )

        for module_name in module_names:
            if module_name not in seen:
                seen.add(module_name)
                yield importlib.import_module(module_name)
