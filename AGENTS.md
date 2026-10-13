# Repository Guidelines

## Project Structure

Python 3.12+ FastAPI starts in `src/main.py`. Shared annotations, configuration,
responses, and errors live in `src/common/`; `src/context.py` and `src/lifespan.py`
manage discovery and initialization. Organize features under `src/features/`
using `api/`, `domain/`, `services/`, and `repositories/`. Keep contracts beside
implementations. Store HTML in `pages/`, automated tests in `test/`, and API
request examples in `http/`.

## Development Commands

- `uv sync`: install locked application dependencies.
- `uv run src/main.py`: start the server; inspect `/docs`.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s test`: run tests.
- `uv run --with pytest pytest`: run through pytest.
- `uv run --with ruff ruff check .`: lint.
- `uv run --with ruff ruff format .`: format.

`make run` also tests, auto-fixes lint, and formats. Install pytest/Ruff separately for these targets.

## Components, ABC Contracts & Dependency Injection

Define service, repository, and router contracts with `ABC` and
`@abstractmethod`; declare typed methods:

```python
from abc import ABC, abstractmethod
from features.tasks.domain.task import Task

class TaskRepository(ABC):
    @abstractmethod
    async def find_all(self) -> list[Task]:
        ...
```

Leave contracts undecorated. Implement every abstract method in concrete classes.
Use `@Component` for repositories, `@Service` for services, and
`@Controller("/tasks")` for routers, imported from `common.annotation.component`,
`.service`, and `.router`. Decorate handlers with `@Get`, `@Post`, `@Put`,
`@Patch`, or `@Delete`. Scanned feature components register automatically.

Inject contracts through typed constructor arguments or handler parameters; avoid manual construction. To select TXT:

```python
from typing import Annotated
from common.annotation.qualifier import Qualifier

# On the concrete repository: @Component and @Qualifier("txt")
def __init__(self, repository: Annotated[TaskRepository, Qualifier("txt")]):
    self.repository = repository
```

Use `@Primary` for a default implementation or `list[TaskRepository]` for all
implementations. Ambiguous single dependencies fail initialization. Preserve the
router → service → repository direction and existing response/error envelopes.

## Style & Testing

Use four spaces, type annotations, `snake_case` files/functions, and `PascalCase`
classes. Keep filesystem work off the event loop; retain locking and atomic writes.

Add API test requests to `http/<feature>.http`, separated by `###`; include methods,
URLs, headers, bodies, filters, and errors. Run via an IDE HTTP client. Follow `http/tasks.http`; retain automated tests.

Automated tests use unittest, async test cases, and HTTPX ASGI clients. Use `test_*.py` / `test_*`, temporary storage, and cover validation, persistence,
concurrency, and DI.

## Commits, PRs & Configuration

Follow recent `feat(scope): description` commits. PRs explain changes, validation,
and relevant issues; include HTTP examples or UI screenshots when applicable.
Copy `.env.example` to `.env`; never commit secrets, logs, or task data. TXT is
selected through its qualifier; changing adapters does not migrate existing tasks.
