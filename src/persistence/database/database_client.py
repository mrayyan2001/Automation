from abc import ABC, abstractmethod

from common.health_check_client import HealthCheckClient


class DatabaseClient(HealthCheckClient, ABC):
    @abstractmethod
    async def aclose(self) -> None: ...
