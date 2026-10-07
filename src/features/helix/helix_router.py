"""Helix pages and API using the same controller conventions as HomeRouter."""

import asyncio
import io
import json
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ValidationError, field_validator

from common.annotation.router import Controller, Get, Post
from features.helix.helix_service import HelixService
from features.helix.helix_excel import build_excel_template, import_excel

PAGE = Path(__file__).resolve().parents[3] / "pages" / "helix.html"
MAX_UPLOAD = 5 * 1024 * 1024


class EnvironmentUpload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    export: dict

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class CreateServiceRequest(BaseModel):
    templateId: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    fieldValues: dict[str, str] = Field(default_factory=dict)
    categoryIds: list[str] = Field(default_factory=list, max_length=3)
    tags: list[str] = Field(default_factory=list, max_length=50)


class CreatePackageRequest(BaseModel):
    services: list[CreateServiceRequest] = Field(min_length=1, max_length=50)


@Controller("/helix")
class HelixRouter:
    def __init__(self, service: HelixService):
        self.service = service

    @Get("/")
    async def page(self) -> FileResponse:
        return FileResponse(PAGE, media_type="text/html")

    @Get("/api/environments")
    async def environments(self) -> list[dict]:
        return await asyncio.to_thread(self.service.list_environments)

    @Post("/api/environments")
    async def upload(self, request: Request) -> dict:
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_UPLOAD:
                raise HTTPException(413, "The upload must be smaller than 5 MB.")
        try:
            upload = EnvironmentUpload.model_validate_json(payload)
        except ValidationError as exc:
            raise HTTPException(400, "Provide an environment name and a valid ServiceExport JSON object.") from exc
        return await asyncio.to_thread(self.service.save_environment, upload.name, upload.export)

    @Get("/api/environments/{environment_id}")
    async def environment(self, environment_id: UUID) -> dict:
        return await asyncio.to_thread(self.service.get_environment, str(environment_id))

    @Post("/api/environments/{environment_id}/services")
    async def create(self, environment_id: UUID, body: CreateServiceRequest) -> dict:
        return await asyncio.to_thread(self.service.create, str(environment_id), body.templateId, body.name, body.fieldValues, body.categoryIds, body.tags)

    @Post("/api/environments/{environment_id}/packages")
    async def create_package(self, environment_id: UUID, body: CreatePackageRequest) -> dict:
        return await asyncio.to_thread(self.service.create_package, str(environment_id), [service.model_dump() for service in body.services])

    @Get("/api/environments/{environment_id}/excel-template")
    async def excel_template(self, environment_id: UUID) -> Response:
        export = await asyncio.to_thread(self.service.get_export, str(environment_id))
        try:
            content = await asyncio.to_thread(build_excel_template, export)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, "Unable to generate the Excel template. Please try again.") from exc
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="Helix-services-template.xlsx"'})

    @Post("/api/environments/{environment_id}/import-excel")
    async def excel_import(self, environment_id: UUID, request: Request) -> dict:
        export = await asyncio.to_thread(self.service.get_export, str(environment_id))
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > MAX_UPLOAD:
                raise HTTPException(413, "The Excel file must be smaller than 5 MB.")
        try:
            return await asyncio.to_thread(import_excel, export, bytes(payload))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @Get("/api/environments/{environment_id}/packages/{package_id}")
    async def download(self, environment_id: UUID, package_id: UUID, format: str = "json") -> Response:
        if format not in ("json", "zip"):
            raise HTTPException(400, "Choose json or zip format.")
        export = await asyncio.to_thread(self.service.get_package, str(environment_id), str(package_id))
        content = json.dumps(export, indent=2, ensure_ascii=False).encode()
        if format == "zip":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ServiceExport.json", content)
            content = buffer.getvalue()
        return Response(content, media_type="application/zip" if format == "zip" else "application/json",
                        headers={"Content-Disposition": f'attachment; filename="ServiceExport.{format}"'})
