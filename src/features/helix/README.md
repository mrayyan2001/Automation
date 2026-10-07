# Helix environment workspace

Open `/helix/` or choose **Helix environments** from the home page.

1. Name an environment and upload its ServiceExport JSON (maximum request size: 5 MB).
2. The upload can have `services: []`; it must include `versionInfo`, `tenantConfig`, `serviceTypes`, and `categories` objects and at least one service template. An existing export also works. The complete uploaded definitions are retained.
3. Open a saved environment, select a template from the environment, fill in the service name and profile fields, optionally select categories, and save the service.
4. Download the saved package as JSON or ZIP containing `ServiceExport.json`.

Environments are identified by the user-supplied name and an application UUID. Build/version information is descriptive metadata, not a reliable tenant or server identity. Environment names are unique without regard to case.

Storage uses SQLite at `data/helix.sqlite3`, ignored by Git. Set `HELIX_DATABASE_PATH` to choose another location. Preserve this database across application restarts/deployments. Each generated package is saved separately; the uploaded environment export is unchanged. A single server/shared filesystem deployment is assumed.

The controller follows `HomeRouter` using `@Controller`, `@Get`, and `@Post`. The annotated `HelixService` is injected through the application's component system and performs storage/generation in a worker thread. No additional dependencies are needed. API responses use the existing success/error envelopes; downloads and page responses are returned directly.

The service form uses the template selected from the current environment and omits Platform. The form creates one free draft service with an isolated Start → End workflow. Text fields, descriptions, and dropdowns come from the chosen environment template. Required fields and dropdown options are validated server-side, and categories must belong to the selected template. Descriptions accept plain text, which is escaped and converted to HTML with line breaks. Templates with required field types beyond text and dropdowns cannot be submitted yet. Optional media and file fields are left empty. Existing saved environments load the expanded form definitions from their original export, so no re-upload is needed. Existing services, questionnaires, logos, connector assignments, and service dependency maps are excluded from generated packages. Environment template/category definitions are retained.

The app does not connect to or create records in Helix. Generated source identifiers and workflow definitions have been checked for internal consistency, but import compatibility has not been tested against a live Helix server. Review and test an import before publishing any service.

See `http/helix.http` for requests. The illustrative minimal payload demonstrates the application API, not a vendor-approved minimum import schema. Use a real exported template for import attempts.

Run checks with `PYTHONPATH=src .venv/bin/python -m unittest discover -s test -v`.

Tags are entered as comma-separated names. Existing unlocalized tags are reused by name without regard to case, and new tags get local source IDs. The downloaded JSON uses the root `tags` map and revision `revisionTags` records (`summary: SbeServiceRevisionTag`, `tagId`, and `locale`), matching `reference/ServiceExport 3.json`. Duplicate names are removed and both revision copies contain the same tag associations.
