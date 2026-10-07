"""Durable environment and generated package storage."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from common.annotation.service import Service
from features.helix.service_generator import create_package, inspect_export

ROOT = Path(__file__).resolve().parents[3]


@Service
class HelixService:
    def __init__(self, database: Path | None = None):
        self.database = database or Path(os.environ.get("HELIX_DATABASE_PATH", ROOT / "data" / "helix.sqlite3"))

    @contextmanager
    def _connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE TABLE IF NOT EXISTS environments (id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, created_at TEXT NOT NULL, summary TEXT NOT NULL, export TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS packages (id TEXT PRIMARY KEY, environment_id TEXT NOT NULL REFERENCES environments(id), created_at TEXT NOT NULL, summary TEXT NOT NULL, export TEXT NOT NULL)")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list_environments(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT id, name, created_at, summary FROM environments ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "name": r["name"], "createdAt": r["created_at"], **json.loads(r["summary"])} for r in rows]

    def save_environment(self, name: str, export: dict) -> dict:
        try:
            summary = inspect_export(export)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        identifier, created = str(uuid4()), datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as db:
                db.execute("INSERT INTO environments VALUES (?, ?, ?, ?, ?)",
                           (identifier, name, created, json.dumps(summary), json.dumps(export)))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "An environment with this name already exists.") from exc
        return {"id": identifier, "name": name, "createdAt": created, **summary}

    def _environment(self, identifier: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM environments WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise HTTPException(404, "Environment not found.")
        return row

    def get_environment(self, identifier: str) -> dict:
        row = self._environment(identifier)
        with self._connect() as db:
            batches = db.execute("SELECT id, created_at, summary FROM packages WHERE environment_id = ? ORDER BY created_at DESC", (identifier,)).fetchall()
        return {"id": row["id"], "name": row["name"], "createdAt": row["created_at"], **inspect_export(json.loads(row["export"])),
                "categories": [{"id": key, "name": value.get("name", key), "parentId": value.get("parentId")} for key, value in json.loads(row["export"])["categories"].items()],
                "tags": [{"id": key, **value} for key, value in json.loads(row["export"]).get("tags", {}).items()],
                "packages": [{"id": b["id"], "createdAt": b["created_at"], **json.loads(b["summary"])} for b in batches]}

    def create(self, identifier: str, template_id: str | None, name: str, field_values: dict, category_ids: list[str], tags: list[str] | None = None) -> dict:
        return self.create_package(identifier, [{"templateId": template_id, "name": name, "fieldValues": field_values,
                                                "categoryIds": category_ids, "tags": tags or []}])

    def create_package(self, identifier: str, services: list[dict]) -> dict:
        row = self._environment(identifier)
        try:
            export = create_package(json.loads(row["export"]), services)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        package_id, created = str(uuid4()), datetime.now(timezone.utc).isoformat()
        summary = {"names": [s["name"] for s in export["services"]], "templateIds": list(dict.fromkeys(s["serviceTypeId"] for s in export["services"])),
                   "tags": [tag["name"] for tag in export["tags"].values()]}
        with self._connect() as db:
            db.execute("INSERT INTO packages VALUES (?, ?, ?, ?, ?)", (package_id, identifier, created, json.dumps(summary), json.dumps(export)))
        return {"id": package_id, "createdAt": created, **summary}

    def get_package(self, identifier: str, package_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT export FROM packages WHERE id = ? AND environment_id = ?", (package_id, identifier)).fetchone()
        if row is None:
            raise HTTPException(404, "Service package not found.")
        return json.loads(row["export"])
