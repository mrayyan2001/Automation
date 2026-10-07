"""Build isolated dummy service packages from an environment's export definitions."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4


def inspect_export(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("The ServiceExport must be a JSON object.")
    for key in ("versionInfo", "tenantConfig", "serviceTypes", "categories"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"The ServiceExport needs a {key} object.")
    if not isinstance(data.get("services", []), list):
        raise ValueError("services must be an array; an empty array is supported.")
    templates = []
    for key, value in data["serviceTypes"].items():
        if not isinstance(value, dict) or not isinstance(value.get("fields"), list):
            raise ValueError("Each service template must contain a fields array.")
        if not isinstance(value.get("name", key), str):
            raise ValueError("Service template names must be text.")
        if value.get("templateType", "SERVICE") != "SERVICE":
            continue
        required = []
        for field in value["fields"]:
            if (not isinstance(field, dict) or not isinstance(field.get("id"), str)
                    or not field["id"] or not isinstance(field.get("type"), str) or not field["type"]):
                raise ValueError("Each template field needs an id and type.")
            if any(field.get(k) is not None and not isinstance(field[k], str) for k in ("name", "title")):
                raise ValueError("Template field names and titles must be text.")
            if field.get("required"):
                required.append({k: field.get(k) for k in ("id", "name", "title", "type")})
        templates.append({"id": key, "name": value.get("name", key), "required": required})
    if not templates:
        raise ValueError("The export has no service templates. Include the template definitions.")
    version = data["versionInfo"].get("versionInfo", {})
    return {
        "version": version.get("sbVersion", "Unknown") if isinstance(version, dict) else "Unknown",
        "templates": templates,
        "categoryCount": len(data["categories"]),
        "sourceServiceCount": len(data.get("services", [])),
    }


def _identity() -> dict:
    guid = "AGG" + uuid4().hex[:27].upper()
    return {"guid": guid, "rxId": guid, "id": str(uuid4().int % 10**14)}


def _workflow(name: str, now: int) -> dict:
    def rx():
        return "rx-" + str(uuid4())

    workflow_id, start, end, flow = (rx() for _ in range(4))
    base = {"lastUpdateTime": now, "lastChangedBy": None, "owner": None,
            "tags": None, "description": None, "overlayGroupId": None, "internal": False}
    return {
        **base, "guid": workflow_id, "name": name, "version": None, "scope": "BUNDLE",
        "overlayGroupId": "1", "flowElements": [
            {**base, "guid": start, "name": "Start", "resourceType": "com.bmc.arsys.rx.services.process.domain.StartEventDefinition"},
            {**base, "guid": end, "name": "End", "event": None, "resourceType": "com.bmc.arsys.rx.services.process.domain.EndEventDefinition"},
            {**base, "guid": flow, "name": "Sequence Flow", "sourceNode": start,
             "targetNode": end, "condition": "", "resourceType": "com.bmc.arsys.rx.services.process.domain.SequenceFlowDefinition"},
        ],
        "inputParams": [], "outputParams": [], "localVariables": [], "contextKeyParam": None,
        "isEnabled": True, "permissions": [{"ownerId": {"value": 0, "type": "GROUP", "name": "Public"}, "type": "EXECUTE"}],
        "layout": json.dumps({"cells": [
            {"id": start[3:], "type": "rx.StartEvent", "position": {"x": 50, "y": 100}, "size": {"width": 30, "height": 30}, "z": 1},
            {"id": end[3:], "type": "rx.EndEvent", "position": {"x": 300, "y": 100}, "size": {"width": 30, "height": 30}, "z": 2},
            {"id": flow[3:], "type": "rx.SequenceFlow", "source": {"id": start[3:]}, "target": {"id": end[3:]}, "z": 3, "flowType": "normal", "labels": []},
        ]}),
        "artifacts": [], "runAsUser": False, "synchronous": True,
        "overlayDescriptor": None, "allowOverlay": False, "localizableStrings": {},
    }


def generate_services(data: dict, template_id: str) -> dict:
    info = inspect_export(data)
    template = next((t for t in info["templates"] if t["id"] == template_id), None)
    if template is None:
        raise ValueError("Choose a template from this environment.")
    text_types = {"MULTILINE_INPUT", "RICH_INPUT", "TEXT_INPUT", "SINGLELINE_INPUT"}
    unsupported = [f["title"] or f["name"] for f in template["required"] if f["type"] not in text_types]
    if unsupported:
        raise ValueError("Dummy generation only supports required text fields. This template also requires: " + ", ".join(map(str, unsupported)))
    # Preserve environment definitions, but never copy existing service content or dependencies.
    output = deepcopy(data)
    preserve = {"versionInfo", "tenantConfig", "serviceTypes", "categories", "documentTypes", "showDisabledServiceQuantities"}
    for key, value in output.items():
        if key not in preserve:
            output[key] = [] if isinstance(value, list) else {} if isinstance(value, dict) else value
    for key in ("services", "selectedServiceIds", "dependedServiceIds", "questionnaires", "systemProcessNames", "documentAttachments"):
        output[key] = []
    for key in ("oldRevisionGuidToSla", "oldRevisionGuidToCostAdjustment", "oldRevisionGuidToLogo", "documents", "medium",
                "oldRevisionGuidToBundleStates", "bundles", "fileIdToContents", "serviceTranslations", "serviceVersionTranslations",
                "serviceRevisionTranslations", "oldGroupIdToQuestionnaireTranslations", "catalogIdToConnection", "connectorIdToConnection",
                "rxConnectionIdToConnectionId", "rcfConnectionIdToConnectionId", "tags", "day2ActionMappedServices", "day2ActionMappedConnections",
                "subCatalogs", "bundleServiceIdToBundledServiceIds", "oldRevisionGuidToServiceDependencies", "oldVersionGuidToCompanyNameMapping",
                "processDefinitionGuidToProcessDefinition", "processDefinitionNameToProcessDefinitionGuid", "processGuidToSubCatalogName",
                "processDefinitionNameToProcessDefinition"):
        output[key] = {}
    output.setdefault("documentTypes", {})
    output.setdefault("showDisabledServiceQuantities", False)
    token = uuid4().hex[:8]
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    for index, label in enumerate(("Access Request", "Equipment Request", "General Assistance"), 1):
        name = f"Demo {label} {token}"
        workflow = _workflow(f"myit-sb:Demo Workflow {token} {index}", now)
        revision = {
            **_identity(), "name": name, "modifiedDate": now, "state": "draft", "workflowId": workflow["guid"],
            "fulfillmentType": "INTERNAL_WORKFLOW", "fulfillmentExternalEmbeddedSupported": False,
            "prices": [{**_identity(), "createDate": None, "modifiedDate": now, "summary": None,
                        "paymentType": "FREE", "price": None, "currency": None, "paymentSchedule": None,
                        "useBundledServicesCosts": False, "freeLabelId": None, "freeLabel": None}],
            "fieldValues": [], "revisionTags": [], "tags": [], "documents": [], "allMappedCategories": [],
            "media": [], "categoryIds": [], "multiRequestBundle": False, "minQuantity": 1, "maxQuantity": 100,
            "enableBundleServiceLevelQuantity": False, "enableQuantity": False, "unavailableRequiredServicesCount": 0,
            "hasDuplicates": False, "hasBundledDependentService": False,
        }
        for field in template["required"]:
            text = f"A dummy {label.lower()} service." if field["name"] == "service_excerpt" else f"Demo {label.lower()}. The workflow starts and ends without additional actions."
            revision["fieldValues"].append({**_identity(), "modifiedDate": now, "serviceTypeFieldId": field["id"],
                                             "value": [f"<p>{text}</p>" if field["type"] == "RICH_INPUT" else text]})
        service_identity = _identity()
        version = {
            **_identity(), "id": service_identity["id"], "revisions": [revision], "name": "", "state": "draft",
            "reopenWorkflowEditEnabled": False, "available": True, "quickRequest": True,
            "importedFromITSM": False, "autoDependent": False, "surveyEnabled": True, "ratingCount": 0,
            "categories": [], "dynamicFields": [], "bundledServices": [], "media": [], "multiRequestBundle": False,
            "score": 0, "bulkRequestedForUserLimit": 1, "unavailableRequiredServicesCount": 0, "translations": [],
            "allowCollaboratorDelegation": False, "allowRequestOnlyForSubmitter": False, "calculatedAvailability": True,
            "anyRevisionMetadataImport": False, "modified": True, "isDependent": False,
        }
        service = {
            **service_identity, "versions": [version], "serviceType": None, "translations": [], "name": name,
            "createDate": None, "modifiedDate": now, "summary": None, "state": "draft", "serviceTypeId": template_id,
            "externalId": None, "catalogId": None, "isAction": False, "subCatalogId": None,
            "allRevisions": [deepcopy(revision)], "modified": False,
        }
        output["services"].append(service)
        output["selectedServiceIds"].append(service["id"])
        output["processDefinitionGuidToProcessDefinition"][workflow["guid"]] = workflow
        output["processDefinitionNameToProcessDefinitionGuid"][workflow["name"]] = workflow["guid"]
        output["processGuidToSubCatalogName"][workflow["guid"]] = None
        for key, obj in (("serviceTranslations", service), ("serviceVersionTranslations", version), ("serviceRevisionTranslations", revision)):
            output[key][obj["guid"]] = []
    return output
