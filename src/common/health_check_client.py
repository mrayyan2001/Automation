from abc import ABC, abstractmethod


class HealthCheckClient(ABC):
    @property
    def health_check_name(self) -> str:
        return type(self).__name__.removesuffix("Client")

    @abstractmethod
    async def health_check(self) -> None: ...
