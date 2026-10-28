from abc import ABC

from common.annotation.service import Service


class HomeService(ABC):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


@Service
class MhHomeService(HomeService):
    def __init__(self):
        super().__init__("MH Company")
