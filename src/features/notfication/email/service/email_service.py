from abc import ABC, abstractmethod


class EmailService(ABC):
    @abstractmethod
    async def send_email(self, receiver: str, subject: str, body: str) -> bool: ...
