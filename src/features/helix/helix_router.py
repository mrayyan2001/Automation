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

PAGE = Path(__file__).resolve().parents[3] / "pages" / "helix.html"
MAX_UPLOAD = 5 * 1024 * 1024


class EnvironmentUpload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    export: dict

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class GenerateRequest(BaseModel):
    templateId: str = Field(min_length=1, max_length=100)


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

    @Post("/api/environments/{environment_id}/generate")
    async def generate(self, environment_id: UUID, body: GenerateRequest) -> dict:
        return await asyncio.to_thread(self.service.generate, str(environment_id), body.templateId)

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
                        headers={"Content-Disposition": f'attachment; filename="ServiceExport-dummy.{format}"'})
