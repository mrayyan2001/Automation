import inspect

from common.annotation.common.discovery import iter_modules


def annotation(name: str):
    def decorator(cls):
        annotations = set(getattr(cls, "__annotations_meta__", set()))
        annotations.add(name)

        cls.__annotations_meta__ = annotations
        return cls

    return decorator


def has_annotation(cls: type, annotation_name: str) -> bool:
    return annotation_name in get_annotations(cls)


def get_annotations(cls: type) -> set[str]:
    return set(getattr(cls, "__annotations_meta__", set()))


def has_any_annotation(cls: type, annotation_names: set[str]) -> bool:
    return bool(get_annotations(cls).intersection(annotation_names))


def scan_annotation(
    annotation_name: str,
    package_name: str | list[str],
) -> list[type]:
    result: set[type] = set()

    for module in iter_modules(package_name):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == module.__name__ and has_annotation(
                cls,
                annotation_name,
            ):
                result.add(cls)

    return list(result)
