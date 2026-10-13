"""Mark the default implementation for single-component injection."""


def Primary(cls: type) -> type:
    cls.__primary__ = True
    return cls
