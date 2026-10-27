# Repository Guidelines

## Project Structure

Python 3.12+ FastAPI starts in `src/main.py`. Shared annotations, configuration,
responses, and errors live in `src/common/`; `src/context.py` and `src/lifespan.py`
manage discovery and initialization. Organize features under `src/features/`
using `api/`, `domain/`, `services/`, and `repositories/`. Store HTML in `pages/`, automated tests in `tests`, and API
request examples in `http/`.

## Package Responsibilities & File Boundaries

Each package must serve one purpose:

- `api/`: HTTP parsing, request/response schemas, routing, and response mapping.
- `domain/`: entities, value types, and domain definitions, independent of HTTP and storage.
- `services/`: business operations, validation, and coordination through repository contracts.
- `repositories/`: persistence contracts and storage adapters; no HTTP handlers.

Create additional subpackages only for distinct responsibilities. Avoid mixing
unrelated features or putting business logic and filesystem access in routers.
Omit unused layers; stateless converters do not need repositories.

Put every ABC contract in its own file and each concrete implementation in a
separate file in the same responsibility package. Examples:

- `services/task_service.py` → `TaskService`; `task_service_impl.py` → `TaskServiceImpl`.
- `repositories/task_repository.py` → `TaskRepository`; `txt_task_repository.py` → `TxtTaskRepository`.
- `api/converter_router.py` → `ConverterRouter`; `converter_router_impl.py` → `ConverterRouterImpl`.

Implementations import and inherit their contracts; contracts must not import
implementations. Keep `__init__.py` focused on package declarations or deliberate
exports, not application logic.

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
    async def find_all(self) -> list[Task]: ...
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
Use `async def` for router handlers, service and repository operations, and
I/O-bound workflows. Await calls between layers and keep blocking I/O off the
event loop.

Add API test requests to `http/<feature>.http` for every endpoint, separated by
`###`; include methods, URLs, headers, bodies, and successful, validation, and
relevant error cases. Run via an IDE HTTP client. Follow `http/tasks.http`; retain
automated tests.

Prefix every API route with `/api/v{version}/` (for example, `/api/v1/tasks`).

Automated tests use unittest, async test cases, and HTTPX ASGI clients. Use `test_*.py` / `test_*`, temporary storage, and cover validation, persistence,
concurrency, and DI.

Always add or update automated test cases for every code change. Run the relevant
tests before finishing and report the results.

## Commits, PRs & Configuration

Follow recent `feat(scope): description` commits. PRs explain changes, validation,
and relevant issues; include HTTP examples or UI screenshots when applicable.
Group related changes into one focused commit, and keep unrelated changes in
separate commits.
Copy `.env.example` to `.env`; never commit secrets, logs, or task data. TXT is
selected through its qualifier; changing adapters does not migrate existing tasks.

# Repository Guidelines

## Change Scope

Prefer the smallest change that solves the task. Keep changes simple and focused, and avoid unrelated refactoring or added complexity.

## Project Structure & Module Organization

The application is a Python 3.12 FastAPI service. Runtime code lives in `src/`, with feature-oriented modules under `src/features/`, shared utilities under `src/common/utils/`, and persistence integrations under `src/persistence/`; `src/main.py` is the entry point. Put reusable helpers used by multiple features in `src/common/utils/`; keep feature-specific behavior with its owning feature. Tests are in `tests/` and mirror major areas such as `config/` and `exception/`. Supporting material includes `examples/` for runnable demonstrations, `pages/` for the builder UI, `bruno/` and `http/` for API request collections, and `litellm/` for LiteLLM configuration. Keep secrets in local `.env` files based on `.env.example`.

## Build, Test, and Development Commands

Use `uv` for dependency and environment management:

- `uv sync` installs the locked project dependencies; use `uv sync --dev` when setting up tests.
- `uv run pytest -v` runs the full test suite with verbose output.
- `make check` runs Ruff checks with safe fixes; `make format` formats Python files with Ruff. Always run both after making changes and before finishing the task.
- `make run` syncs dependencies, tests, checks, formats, and starts the service.
- `uv run python src/main.py` starts the service directly. Local API docs are at `/docs` and `/redoc`.
- `docker compose up` starts the containerized service and configured dependencies.

## Coding Style & Naming Conventions

Use 4-space indentation, readable type annotations, and small feature-focused modules. Follow Ruff’s configured formatting and linting decisions. Use `snake_case` for Python modules, functions, and variables; `PascalCase` for classes and Pydantic models; and uppercase names for environment variables. Keep public API models and control-specific models close to their feature implementation.

## Design Principles

- Keep files, classes, functions, and code chunks small and focused. Split large files and classes into cohesive units; split long functions into named steps that each do one task. Avoid arbitrary line-count limits.
- Follow SOLID principles: give each class and module one clear responsibility, depend on abstractions where useful, and keep components open to extension without coupling unrelated features.
- Keep related behavior together and extract shared code only when it has multiple real callers. Avoid oversized utility modules and premature abstractions.
- Keep the codebase free of warnings and errors reported by configured checks and IDE inspections. Run the checks after changes and resolve or narrowly suppress intentional, tool-specific false positives with a clear reason.

## Testing Guidelines

Tests use `pytest` and may be marked with the registered `unit` marker (for example, `pytest -m unit`). Name files `test_*.py` and test functions `test_*`. Add regression coverage for changed behavior, especially configuration loading, API handlers, and builder/control models. Run `uv run pytest -v` before opening a pull request.

## Commit & Pull Request Guidelines

Do not create commits unless the user explicitly asks for them. When asked to commit, commit all outstanding changes in the working tree unless the user explicitly limits the scope. Split the work into focused commits grouped by related changes; do not combine unrelated features or fixes. Continue to exclude secrets, credentials, tokens, and generated logs. Use flat branch names without slash-separated prefixes such as `feature/` or `fix/`. Recent history follows Conventional Commits with a scope, such as `feat(builder): ...`, `refactor(builder): ...`, and `style(builder): ...`. Use an imperative, focused subject and keep unrelated changes separate. Pull requests should explain the behavior change, identify configuration or API impacts, link the relevant issue when available, and include tests or request examples; attach screenshots for builder UI changes.

## Security & Configuration

Never commit `.env`, credentials, tokens, or generated logs. Update `.env.example` when adding required configuration, document defaults clearly, and verify environment-specific YAML overrides before testing locally.

## Centralized Configuration & Defaults

- Keep all application configuration and runtime default values in `src/common/config/common.yaml`. Use environment-specific YAML files for overrides and environment-variable references for secrets and deployment-specific values.
- Do not hardcode configurable values in Python or UI code. This includes endpoints, model names, token budgets, temperatures, timeouts, retry policies, concurrency, batch sizes, upload limits, cache sizes, retention periods, and feature settings.
- Treat `common.yaml` as the single source of defaults. Do not duplicate defaults in settings models, function arguments, constants, `.get()` fallbacks, or environment-variable reads. Require and validate configuration values, then pass the loaded settings to consumers.
- When adding or changing behavior, add the corresponding configuration to `common.yaml`, wire it through the relevant settings model, and remove superseded or unused configuration. Derive limit-related messages from the configured values.
- Build test settings from the canonical YAML defaults and override only the values relevant to each test. Keep fixed protocol identifiers, mathematical constants, and test fixture data in code only when they are not application configuration or runtime defaults.
