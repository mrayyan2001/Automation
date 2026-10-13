from typing import Annotated

from common.annotation.qualifier import Qualifier
from common.annotation.service import Service
from references.book_catalog.repositories.book_repository import BookRepository
from references.book_catalog.services.book_service_impl import BookServiceImpl


@Service
@Qualifier("json")
class JsonBookServiceImpl(BookServiceImpl):
    # Reuse business operations; only the injected adapter and its label differ.
    def __init__(
        self, repository: Annotated[BookRepository, Qualifier("json")]
    ) -> None:
        super().__init__(repository)

    @property
    def backend(self) -> str:
        return "json"
