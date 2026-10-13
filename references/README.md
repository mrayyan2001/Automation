# Feature reference: book catalog

A runnable feature demonstrating the repository's router → service → repository architecture. All ABC interfaces are undecorated and have their own files; concrete implementations live in separate files. The example stays outside `src/features`, so the production app does not discover it automatically.

## Run

From the repository root:

```bash
uv sync
PYTHONPATH=src:. uv run uvicorn references.book_catalog.app:app --port 8012
```

Open `http://localhost:8012/docs`. Send requests from [book_catalog.http](book_catalog/book_catalog.http). The example has no authentication; it demonstrates storage and dependency injection. Its startup completes discovery before accepting requests.

Data lives in `data/reference_books/`. Override `REFERENCE_DATA_DIR` to use another directory. SQLite and JSON have separate datasets: selecting an adapter does not copy or migrate records.

## Files and responsibilities

```text
book_catalog/
├── app.py                            standalone runner and DI discovery
├── api/
│   ├── book_router.py                ABC router interface
│   ├── book_router_impl.py           HTTP handlers and service injection
│   └── schemas.py                    request validation
├── domain/
│   └── book.py                       immutable domain entity
├── services/
│   ├── book_service.py               ABC service interface
│   ├── book_service_impl.py          business rules, default SQLite service
│   └── json_book_service_impl.py     same business rules, JSON dependency
└── repositories/
    ├── book_repository.py            ABC persistence interface
    ├── sqlite_book_repository.py     transactional SQL adapter
    └── json_book_repository.py       locked JSON adapter with atomic writes
```

`JsonBookServiceImpl` inherits the concrete business operations from `BookServiceImpl`, which implements `BookService`. Its constructor overrides repository selection; its backend property identifies the adapter. The injector checks `@Primary` on each concrete class, so the JSON subclass does not become primary through inheritance.

## Dependency selection

| Injection | Result |
| --- | --- |
| `service: BookService` | `BookServiceImpl`, selected with `@Primary` |
| `repository: Annotated[BookRepository, Qualifier("sqlite")]` | `SqliteBookRepository` |
| `repository: Annotated[BookRepository, Qualifier("json")]` | `JsonBookRepository` |
| `service: Annotated[BookService, Qualifier("json")]` | `JsonBookServiceImpl`; shown in handler parameters |
| `services: list[BookService]` | Both service implementations, shown in the router constructor |

Qualifiers are declared on implementations with `@Qualifier("sqlite")` or `@Qualifier("json")`. `GET /reference/books/backends` calls each injected service and returns its record count. Lists include all implementations regardless of `@Primary`; do not rely on their ordering. Without a qualifier or a unique primary, multiple candidates cause initialization to fail.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/reference/books` | List SQLite books through the default service |
| POST | `/reference/books` | Create a SQLite book |
| GET | `/reference/books/{book_id}` | Find a SQLite book or return 404 |
| DELETE | `/reference/books/{book_id}` | Delete a SQLite book or return 404 |
| GET | `/reference/books/json` | List JSON books through a qualified handler dependency |
| POST | `/reference/books/json` | Create a JSON book through a qualified handler dependency |
| GET | `/reference/books/backends` | Query every injected service |

Specific routes are registered before `/{book_id}` to avoid treating `json` or `backends` as a book ID. Results use the existing success/error envelopes. Repository `save` supports insert or replacement; this example exposes creation, listing, retrieval, and deletion over HTTP.

All runtime filesystem and SQLite work uses `asyncio.to_thread`. SQL writes commit or roll back within transactions. JSON reads and writes acquire a cross-process sidecar lock, and writes flush to a temporary file before atomic replacement. This JSON adapter uses Unix `fcntl`, matching this Linux workspace; use a cross-platform locking library for Windows. Invalid JSON raises an error rather than silently discarding existing data.

## Validation

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s test
uv run --with ruff ruff check references test/test_reference_books.py
```

The tests use temporary storage and cover DI selection, list injection, both HTTP backends, persistence after reopening, concurrent JSON writes, input validation, and missing records.

To reuse this feature inside the main app, copy `book_catalog` to `src/features/book_catalog` and change `references.book_catalog` imports to `features.book_catalog`. Leave `app.py` behind; the main app already discovers feature components and controllers. Selecting a new default means moving `@Primary` to the intended implementation or explicitly qualifying the consuming dependency.
