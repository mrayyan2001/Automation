"""Build service packages from an environment's export definitions."""

from copy import deepcopy
from datetime import datetime, timezone
from html import escape
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
    if not isinstance(data.get("tags", {}), dict) or any(
        not isinstance(tag, dict) or not isinstance(tag.get("name"), str)
        for tag in data.get("tags", {}).values()
    ):
        raise ValueError("tags must be an object containing tag names.")
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
        templates.append({"id": key, "name": value.get("name", key), "required": required,
                          "fields": deepcopy(value["fields"]), "categoryIds": value.get("categories", [])})
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


def create_service(data: dict, template_id: str | None, name: str, field_values: dict, category_ids: list[str], tags: list[str] | None = None) -> dict:
    info = inspect_export(data)
    if template_id is None and len(info["templates"]) == 1:
        template_id = info["templates"][0]["id"]
    template = next((t for t in info["templates"] if t["id"] == template_id), None)
    if template is None:
        raise ValueError("Choose a service template from this environment.")
    name = name.strip()
    if not name or len(name) > 200:
        raise ValueError("Enter a service name (1–200 characters).")
    fields = {f["id"]: f for f in template["fields"] if str(f.get("name", "")).casefold() != "platform" and str(f.get("title", "")).casefold() != "platform"}
    if set(field_values) - set(fields):
        raise ValueError("A profile field does not belong to this environment's template.")
    text_types = {"MULTILINE_INPUT", "RICH_INPUT", "TEXT_INPUT", "SINGLELINE_INPUT"}
    values = {}
    for field_id, field in fields.items():
        value = field_values.get(field_id, "")
        title = field.get("title") or field.get("name") or field_id
        if not isinstance(value, str) or len(value) > 20000:
            raise ValueError(f"{title} must be text with at most 20,000 characters.")
        value = value.strip()
        if field.get("required") and not value:
            raise ValueError(f"{title} is required.")
        if not value:
            continue
        if field["type"] == "DROPDOWN":
            options = {o.get("name") for o in field.get("params", {}).get("form_values", []) if isinstance(o, dict)}
            if value not in options:
                raise ValueError(f"Choose a valid option for {title}.")
        elif field["type"] not in text_types:
            raise ValueError(f"{title} cannot be configured in this form yet.")
        values[field_id] = "<p>" + escape(value).replace("\n", "<br>") + "</p>" if field["type"] == "RICH_INPUT" else value
    allowed_categories = set(template["categoryIds"]) & set(data["categories"])
    if set(category_ids) - allowed_categories:
        raise ValueError("Choose categories available to this environment's template.")
    selected_tags = {}
    available_tags = data.get("tags", {})
    for tag in tags or []:
        if not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 100:
            raise ValueError("Each tag must contain 1–100 characters.")
        tag = tag.strip()
        if tag.casefold() in {t["name"].casefold() for t in selected_tags.values()}:
            continue
        existing = next(((key, value) for key, value in available_tags.items()
                         if isinstance(value, dict) and isinstance(value.get("name"), str)
                         and value["name"].casefold() == tag.casefold() and value.get("locale") is None), None)
        if existing:
            selected_tags[existing[0]] = deepcopy(existing[1])
        else:
            identifier = _identity()["id"]
            while identifier in available_tags or identifier in selected_tags:
                identifier = _identity()["id"]
            selected_tags[identifier] = {"name": tag, "locale": None}
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
    output["tags"] = selected_tags
    token = uuid4().hex[:8]
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    workflow = _workflow(f"myit-sb:Service Workflow {token}", now)
    revision = {
        **_identity(), "name": name, "modifiedDate": now, "state": "draft", "workflowId": workflow["guid"],
        "fulfillmentType": "INTERNAL_WORKFLOW", "fulfillmentExternalEmbeddedSupported": False,
        "prices": [{**_identity(), "createDate": None, "modifiedDate": now, "summary": None,
                    "paymentType": "FREE", "price": None, "currency": None, "paymentSchedule": None,
                    "useBundledServicesCosts": False, "freeLabelId": None, "freeLabel": None}],
        "fieldValues": [], "revisionTags": [], "tags": [], "documents": [], "allMappedCategories": [],
        "media": [], "categoryIds": list(dict.fromkeys(category_ids)), "multiRequestBundle": False, "minQuantity": 1, "maxQuantity": 100,
        "enableBundleServiceLevelQuantity": False, "enableQuantity": False, "unavailableRequiredServicesCount": 0,
        "hasDuplicates": False, "hasBundledDependentService": False,
    }
    for field_id, value in values.items():
        revision["fieldValues"].append({**_identity(), "modifiedDate": now, "serviceTypeFieldId": field_id, "value": [value]})
    revision["revisionTags"] = [
        {**_identity(), "createDate": now, "modifiedDate": now, "summary": "SbeServiceRevisionTag",
         "tagId": tag_id, "locale": tag["locale"]}
        for tag_id, tag in selected_tags.items()
    ]
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
