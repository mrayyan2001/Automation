from abc import ABC

from common.annotation.service import Service


class HomeService(ABC):
    def __init__(self, name: str, tags: list[str]) -> None:
        self._name = name
        self._tags = tags

    @property
    def name(self) -> str:
        return self._name

    @property
    def tags(self) -> list[str]:
        return self._tags


@Service
class MhHomeService(HomeService):
    def __init__(self):
        super().__init__("MH Company", ["IT", "AI"])
