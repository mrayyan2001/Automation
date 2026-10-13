"""Name a component or select it with Annotated[ServiceType, Qualifier(name)]."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Qualifier:
    name: str

    def __call__(self, cls: type) -> type:
        cls.__qualifier__ = self.name
        return cls
