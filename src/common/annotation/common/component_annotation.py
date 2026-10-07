from common.annotation.common.annotation import annotation

COMPONENT_ANNOTATIONS = set[str]()


def component_annotation(name: str):
    COMPONENT_ANNOTATIONS.add(name)

    def decorator(cls):
        return annotation(name)(cls)

    return decorator
