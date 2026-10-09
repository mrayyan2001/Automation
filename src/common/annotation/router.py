"""Routers that automatically inject annotated application components."""

import inspect
from functools import wraps
from time import sleep
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from starlette.responses import Response

from common.annotation.common.annotation import (
    has_any_annotation,
)
from common.annotation.common.component_annotation import (
    COMPONENT_ANNOTATIONS,
    component_annotation,
)
from common.annotation.common.discovery import iter_modules
from common.annotation.fastapi_di import get_bean
from common.response import SuccessResponse

controller_component = component_annotation("controller")


def _route(method: str, path: str):
    """Mark a controller method with an HTTP method and path."""

    def decorator(handler: Any) -> Any:
        handler.__route__ = (method, path)
        return handler

    return decorator


def Get(path: str):
    """Mark a controller method as a ``GET`` endpoint."""

    return _route("get", path)


def Post(path: str):
    """Mark a controller method as a ``POST`` endpoint."""

    return _route("post", path)


def is_component(cls: type) -> bool:
    """Return whether a class carries one of the registered component markers."""

    return has_any_annotation(cls, COMPONENT_ANNOTATIONS)


class ComponentRoute(APIRoute):
    """An APIRoute that turns component-typed parameters into dependencies."""

    def __init__(self, path: str, endpoint: Any, **kwargs: Any) -> None:
        signature = inspect.signature(endpoint)
        parameters = []

        for parameter in signature.parameters.values():
            dependency_type = parameter.annotation
            if (
                inspect.isclass(dependency_type)
                and is_component(dependency_type)
                and parameter.default is inspect.Parameter.empty
            ):
                parameter = parameter.replace(
                    default=Depends(get_bean(dependency_type)),
                )
            parameters.append(parameter)

        endpoint.__signature__ = signature.replace(parameters=parameters)
        super().__init__(path=path, endpoint=endpoint, **kwargs)


class AppRouter(APIRouter):
    """Application router with automatic component injection enabled."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", ComponentRoute)
        super().__init__(*args, **kwargs)


def _controller_endpoint(controller_cls: type, method: Any) -> Any:
    """Create a FastAPI endpoint that invokes a dependency-injected controller."""

    method_signature = inspect.signature(method, eval_str=True)
    parameters = list(method_signature.parameters.values())
    if parameters and parameters[0].name == "self":
        parameters = parameters[1:]

    controller_parameter = inspect.Parameter(
        "controller",
        inspect.Parameter.KEYWORD_ONLY,
        annotation=controller_cls,
    )

    @wraps(method)
    async def endpoint(controller: Any, **kwargs: Any) -> Any:
        result = method(controller, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, Response):
            return result
        return {"success": True, "data": result}

    return_type = method_signature.return_annotation
    if return_type is inspect.Signature.empty:
        return_type = Any
    if return_type is None:
        return_type = type(None)
    if not (inspect.isclass(return_type) and issubclass(return_type, Response)):
        return_type = SuccessResponse[return_type]

    endpoint.__signature__ = inspect.Signature(
        [*parameters, controller_parameter],
        return_annotation=return_type,
    )
    return endpoint


def Controller(prefix: str, **router_kwargs: Any):
    """Register controller routes with a readable tag derived from the module."""

    def decorator(cls: type) -> type:
        cls = controller_component(cls)
        module_name = cls.__module__.rsplit(".", 1)[-1]
        tag = module_name.removesuffix("_router").removesuffix("_controller")
        tag = tag.replace("_", " ").title()
        kwargs = {"tags": [tag], **router_kwargs}
        router = AppRouter(prefix=prefix.rstrip("/"), **kwargs)

        for method in vars(cls).values():
            route = getattr(method, "__route__", None)
            if route is None:
                continue

            http_method, path = route
            router.add_api_route(
                path,
                _controller_endpoint(cls, method),
                methods=[http_method.upper()],
            )

        cls.__router__ = router
        return cls

    return decorator


def scan_routers(packages: str | list[str]) -> list[AppRouter]:
    """Find application routers declared in the supplied packages."""

    routers: dict[int, AppRouter] = {}

    for module in iter_modules(packages):
        for value in vars(module).values():
            if isinstance(value, AppRouter):
                routers[id(value)] = value
            elif inspect.isclass(value):
                router = getattr(value, "__router__", None)
                if isinstance(router, AppRouter):
                    routers[id(router)] = router

    return list(routers.values())


def include_scanned_routers(app: Any, packages: str | list[str]) -> None:
    """Include every discovered ``AppRouter`` in a FastAPI application."""

    for router in scan_routers(packages):
        app.include_router(router)
