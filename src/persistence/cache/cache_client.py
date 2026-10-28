from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

from common.health_check_client import HealthCheckClient


class CacheClient(HealthCheckClient, ABC):
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: timedelta) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> Any: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
