"""Exercise the environment workflow through the application's controller layer."""

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI
from starlette.exceptions import HTTPException

from common.exception.global_exception_handler import http_exception_handler
from context import ApplicationContext
from features.helix.helix_router import HelixRouter
from features.helix.helix_service import HelixService

ROOT = Path(__file__).resolve().parents[1]


class HelixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "helix.sqlite3"
        self.service = HelixService(self.database)
        app = FastAPI()
        app.add_exception_handler(HTTPException, http_exception_handler)
        app.include_router(HelixRouter.__router__)
        app.state.context = ApplicationContext()
        app.state.context.beans[HelixService] = self.service
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.directory.cleanup()

    async def test_empty_exports_generate_and_download_isolated_packages(self):
        for index in (1, 2):
            with self.subTest(export=index):
                source = json.loads((ROOT / "reference" / f"ServiceExport {index}.json").read_text())
                source["services"] = []
                saved = await self.client.post("/helix/api/environments", json={"name": f"Environment {index}", "export": source})
                self.assertEqual(saved.status_code, 200, saved.text)
                environment = saved.json()["data"]
                identifier = environment["id"]
                template_id = environment["templates"][0]["id"]
                generated = await self.client.post(f"/helix/api/environments/{identifier}/generate", json={"templateId": template_id})
                self.assertEqual(generated.status_code, 200, generated.text)
                package = generated.json()["data"]
                url = f"/helix/api/environments/{identifier}/packages/{package['id']}"
                download = await self.client.get(url)
                export = download.json()
                self.assertEqual(len(export["services"]), 3)
                self.assertEqual(export["versionInfo"], source["versionInfo"])
                self.assertEqual(export["serviceTypes"], source["serviceTypes"])
                self.assertEqual(export["categories"], source["categories"])
                identities = set()
                for service in export["services"]:
                    revision = service["versions"][0]["revisions"][0]
                    self.assertEqual(service["allRevisions"], [revision])
                    self.assertEqual(revision["state"], "draft")
                    self.assertEqual(revision["prices"][0]["paymentType"], "FREE")
                    self.assertNotIn("questionnaireGroupId", revision)
                    self.assertNotIn("logoId", revision)
                    self.assertIn(service["id"], export["selectedServiceIds"])
                    self.assertIn(revision["workflowId"], export["processDefinitionGuidToProcessDefinition"])
                    self.assertEqual({f["serviceTypeFieldId"] for f in revision["fieldValues"]},
                                     {f["id"] for f in environment["templates"][0]["required"]})
                    for obj in (service, service["versions"][0], revision):
                        self.assertNotIn(obj["guid"], identities)
                        identities.add(obj["guid"])
                self.assertFalse(export["oldRevisionGuidToLogo"])
                self.assertFalse(export["questionnaires"])
                zip_response = await self.client.get(url + "?format=zip")
                with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                    self.assertEqual(json.loads(archive.read("ServiceExport.json")), export)
                # A fresh storage instance reads the saved environment and package after restart.
                restored = HelixService(self.database).get_environment(identifier)
                self.assertEqual(restored["packages"][0]["id"], package["id"])
                second = await self.client.post(f"/helix/api/environments/{identifier}/generate", json={"templateId": template_id})
                self.assertTrue(set(second.json()["data"]["names"]).isdisjoint(package["names"]))
                missing = await self.client.get(f"/helix/api/environments/{uuid4()}/packages/{package['id']}")
                self.assertEqual(missing.status_code, 404)
        self.assertEqual(len((await self.client.get("/helix/api/environments")).json()["data"]), 2)

    async def test_invalid_upload_duplicate_and_template_errors(self):
        for body in ({"name": "Bad", "export": {}}, {"name": " ", "export": {}}, {"name": "Bad", "export": {"serviceTypes": []}}):
            response = await self.client.post("/helix/api/environments", json=body)
            self.assertEqual(response.status_code, 400)
        response = await self.client.post("/helix/api/environments", content=b"x" * (5 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        source = json.loads((ROOT / "reference" / "ServiceExport 1.json").read_text())
        environment = self.service.save_environment("Development", source)
        duplicate = await self.client.post("/helix/api/environments", json={"name": " development ", "export": source})
        self.assertEqual(duplicate.status_code, 409)
        response = await self.client.post(f"/helix/api/environments/{environment['id']}/generate", json={"templateId": "missing"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.service.get_environment(environment["id"])["packages"], [])
        self.assertEqual((await self.client.get("/helix/")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
