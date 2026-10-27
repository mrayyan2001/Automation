"""Interpret component dependency annotations shared by constructors and routes."""

import inspect
from abc import ABC
from typing import Annotated, get_args, get_origin

from common.annotation.common.annotation import has_any_annotation
from common.annotation.common.component_annotation import COMPONENT_ANNOTATIONS
from common.annotation.qualifier import Qualifier


def dependency_spec(annotation):
    qualifier = None
    if get_origin(annotation) is Annotated:
        annotation, *metadata = get_args(annotation)
        qualifiers = [item.name for item in metadata if isinstance(item, Qualifier)]
        if len(qualifiers) > 1:
            raise TypeError("Only one Qualifier is allowed per dependency")
        qualifier = qualifiers[0] if qualifiers else None
    many = get_origin(annotation) is list
    bean_type = get_args(annotation)[0] if many else annotation
    return bean_type, many, qualifier


def is_component_dependency(annotation):
    bean_type, _, qualifier = dependency_spec(annotation)
    if not inspect.isclass(bean_type):
        return False
    if qualifier is not None or issubclass(bean_type, ABC):
        return True
    pending = [bean_type]
    while pending:
        candidate = pending.pop()
        if has_any_annotation(candidate, COMPONENT_ANNOTATIONS):
            return True
        pending.extend(candidate.__subclasses__())
    return False
