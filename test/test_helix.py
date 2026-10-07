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

    async def test_empty_exports_create_and_download_service_packages(self):
        for index in (1, 3):
            with self.subTest(export=index):
                source = json.loads((ROOT / "reference" / f"ServiceExport {index}.json").read_text())
                source["services"] = []
                saved = await self.client.post("/helix/api/environments", json={"name": f"Environment {index}", "export": source})
                self.assertEqual(saved.status_code, 200, saved.text)
                environment = saved.json()["data"]
                identifier = environment["id"]
                template_id = environment["templates"][0]["id"]
                generated = await self.client.post(f"/helix/api/environments/{identifier}/services", json={"templateId": template_id, "name": "Laptop Request", "fieldValues": {f["id"]: "Requested profile text" for f in environment["templates"][0]["required"]}, "categoryIds": []})
                self.assertEqual(generated.status_code, 200, generated.text)
                package = generated.json()["data"]
                url = f"/helix/api/environments/{identifier}/packages/{package['id']}"
                download = await self.client.get(url)
                export = download.json()
                self.assertEqual(len(export["services"]), 1)
                self.assertEqual(export["versionInfo"], source["versionInfo"])
                self.assertEqual(export["serviceTypes"], source["serviceTypes"])
                self.assertEqual(export["categories"], source["categories"])
                identities = set()
                for service in export["services"]:
                    revision = service["versions"][0]["revisions"][0]
                    self.assertEqual(service["allRevisions"], [revision])
                    self.assertEqual(service["name"], "Laptop Request")
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
                second = await self.client.post(f"/helix/api/environments/{identifier}/services", json={"templateId": template_id, "name": "VPN Request", "fieldValues": {f["id"]: "Second profile text" for f in environment["templates"][0]["required"]}})
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
        response = await self.client.post(f"/helix/api/environments/{environment['id']}/services", json={"templateId": "missing", "name": "Test"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.service.get_environment(environment["id"])["packages"], [])
        self.assertEqual((await self.client.get("/helix/")).status_code, 200)

    async def test_form_fields_categories_and_validation(self):
        source = json.loads((ROOT / "reference" / "ServiceExport 3.json").read_text())
        environment = self.service.save_environment("IT Request", source)
        identifier = environment["id"]
        detail = (await self.client.get(f"/helix/api/environments/{identifier}")).json()["data"]
        template = detail["templates"][0]
        self.assertIn("fields", template)
        self.assertTrue(detail["categories"])
        endpoint = f"/helix/api/environments/{identifier}/services"
        values = {f["id"]: "User supplied text" for f in template["required"]}
        category = next(c["id"] for c in detail["categories"] if c["id"] in template["categoryIds"])
        body = {"name": "New IT Request", "templateId": template["id"], "fieldValues": values, "categoryIds": [category]}
        for change in ({"fieldValues": {}}, {"name": " "}, {"categoryIds": ["missing"]},
                       {"fieldValues": {**values, "missing": "x"}}, {"tags": [" "]}, {"tags": ["x" * 101]}):
            response = await self.client.post(endpoint, json={**body, **change})
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.service.get_environment(identifier)["packages"], [])
        rich = next(f for f in template["fields"] if f["type"] == "RICH_INPUT")
        body["fieldValues"] = {**values, rich["id"]: "<script>alert(1)</script>\nSecond line"}
        body.pop("templateId")
        body["tags"] = ["t1", " T1 ", "t2", "New tag"]
        response = await self.client.post(endpoint, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        package = self.service.get_package(identifier, response.json()["data"]["id"])
        revision = package["services"][0]["allRevisions"][0]
        fields = {f["serviceTypeFieldId"]: f["value"][0] for f in revision["fieldValues"]}
        self.assertEqual(fields[rich["id"]], "<p>&lt;script&gt;alert(1)&lt;/script&gt;<br>Second line</p>")
        self.assertEqual(revision["categoryIds"], [category])
        self.assertEqual(package["services"][0]["serviceTypeId"], template["id"])
        self.assertEqual(package["tags"]["1601"], source["tags"]["1601"])
        self.assertEqual(package["tags"]["1602"], source["tags"]["1602"])
        self.assertEqual(len(package["tags"]), 3)
        self.assertEqual({t["name"] for t in package["tags"].values()}, {"t1", "t2", "New tag"})
        self.assertEqual({t["tagId"] for t in revision["revisionTags"]}, set(package["tags"]))
        self.assertTrue(all(t["summary"] == "SbeServiceRevisionTag" and t["locale"] is None for t in revision["revisionTags"]))
        self.assertEqual(revision, package["services"][0]["versions"][0]["revisions"][0])

    async def test_environment_templates_and_no_platform(self):
        source = json.loads((ROOT / "reference" / "ServiceExport 2.json").read_text())
        environment = self.service.save_environment("Desktop only", source)
        endpoint = f"/helix/api/environments/{environment['id']}/services"
        body = {"name": "Desktop request", "templateId": "2", "fieldValues": {"3": "Excerpt", "5": "Description"}}
        response = await self.client.post(endpoint, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        package = self.service.get_package(environment["id"], response.json()["data"]["id"])
        self.assertEqual(package["services"][0]["serviceTypeId"], "2")
        rejected = await self.client.post(endpoint, json={**body, "fieldValues": {**body["fieldValues"], "6": "Windows"}})
        self.assertEqual(rejected.status_code, 400)
        it_source = json.loads((ROOT / "reference" / "ServiceExport 1.json").read_text())
        source["serviceTypes"].update(it_source["serviceTypes"])
        source["categories"].update(it_source["categories"])
        combined = self.service.save_environment("Combined", source)
        endpoint = f"/helix/api/environments/{combined['id']}/services"
        for template_id, values in (("1", {"1": "Excerpt", "2": "Description"}), ("2", {"3": "Excerpt", "5": "Description"})):
            response = await self.client.post(endpoint, json={"name": "Service " + template_id, "templateId": template_id, "fieldValues": values})
            self.assertEqual(response.status_code, 200, response.text)
            package = self.service.get_package(combined["id"], response.json()["data"]["id"])
            self.assertEqual(package["services"][0]["serviceTypeId"], template_id)
        missing = await self.client.post(endpoint, json={"name": "Missing template", "fieldValues": {}})
        self.assertEqual(missing.status_code, 400)


if __name__ == "__main__":
    unittest.main()
