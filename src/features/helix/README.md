# Helix environment workspace

Open `/helix/` or choose **Helix environments** from the home page.

1. Name an environment and upload its ServiceExport JSON (maximum request size: 5 MB).
2. The upload can have `services: []`; it must include `versionInfo`, `tenantConfig`, `serviceTypes`, and `categories` objects and at least one service template. An existing export also works. The complete uploaded definitions are retained.
3. Open a saved environment, select a template from the environment, fill in the service name and profile fields, optionally select categories, and choose **Add to package**. Repeat for additional services, then choose **Save package**.
4. Download the saved package as JSON or ZIP containing `ServiceExport.json`.

Environments are identified by the user-supplied name and an application UUID. Build/version information is descriptive metadata, not a reliable tenant or server identity. Environment names are unique without regard to case.

Storage uses SQLite at `data/helix.sqlite3`, ignored by Git. Set `HELIX_DATABASE_PATH` to choose another location. Preserve this database across application restarts/deployments. Each generated package is saved separately; the uploaded environment export is unchanged. A single server/shared filesystem deployment is assumed.

The controller follows `HomeRouter` using `@Controller`, `@Get`, and `@Post`. The annotated `HelixService` is injected through the application's component system and performs storage/generation in a worker thread. Excel import uses the declared openpyxl/defusedxml dependencies. Template generation and import both use the installed Python Excel library; no external runtime is required. API responses use the existing success/error envelopes; downloads and page responses are returned directly.

The service form uses the template selected from the current environment and omits Platform. Each entry creates a free draft service with an isolated Start → QAnswer → End workflow. Text fields, descriptions, and dropdowns come from the chosen environment template. Required fields and dropdown options are validated server-side, and categories must belong to the selected template. Descriptions accept plain text, which is escaped and converted to HTML with line breaks. Templates with required field types beyond text and dropdowns cannot be submitted yet. Optional media and file fields are left empty. Existing saved environments load the expanded form definitions from their original export, so no re-upload is needed. Existing services, questionnaires, logos, connector assignments, and service dependency maps are excluded from generated packages. Environment template/category definitions are retained.

The app does not connect to or create records in Helix. Generated source identifiers and workflow definitions have been checked for internal consistency, but import compatibility has not been tested against a live Helix server. Review and test an import before publishing any service.

See `http/helix.http` for requests. The illustrative minimal payload demonstrates the application API, not a vendor-approved minimum import schema. Use a real exported template for import attempts.

Run checks with `PYTHONPATH=src .venv/bin/python -m unittest discover -s test -v`.

Tags are entered as comma-separated names. Existing unlocalized tags are reused by name without regard to case, and new tags get local source IDs. The downloaded JSON uses the root `tags` map and revision `revisionTags` records (`summary: SbeServiceRevisionTag`, `tagId`, and `locale`), matching `reference/ServiceExport 3.json`. Duplicate names are removed and both revision copies contain the same tag associations.

A package can contain 1–50 services from the same environment, with different templates if needed. Names must be unique within the package. The package is validated as a whole before saving: an invalid entry creates no package. Shared tags are reused across services; service, revision, translation, and workflow references are merged into one ServiceExport. The visible new-package queue is an unsaved draft, retained while switching environments on the page; save it before reloading or leaving. Existing single-service packages remain downloadable.


## Excel template and import

Inside an environment, choose **Download Excel template**. The `.xlsx` file contains a single `Services` table (one service per row), without colored cell backgrounds. Service type and categories have dropdown lists; their source values are stored in hidden columns on the same sheet. Keep the table headers unchanged. Choose a service type from the `Service template` dropdown (or enter its environment ID), fill that template's required profile columns, and leave other templates' columns blank. Use Category 1, Category 2, and Category 3 for up to three selections per service; each dropdown accepts a category path or ID. tags use comma-separated names. Platform is excluded.

Choose **Import services from Excel** to validate and add rows to the unsaved package. Import does not create packages or change environment definitions. If any row is invalid, no rows are added; the page displays the row numbers and errors. Existing draft names must not conflict with imported names. The package remains limited to 50 services. Review the imported entries, then save and download the combined package.

The import endpoint accepts raw `.xlsx` bytes, not multipart data, with a 5 MB limit. Expanded ZIP content is limited to 20 MB. Formulas and Excel errors are rejected rather than using potentially stale cached values. Legacy `.xls` and macro-enabled workbooks are not supported.

Template generation runs in Python with openpyxl. It needs no Node executable, Codex runtime, subprocess, or spreadsheet runtime configuration. Dropdown options use named ranges in hidden columns on Services, so long lists and names containing commas remain usable. There is no Reference tab. Each of the three category columns has its own dropdown. Older files with a Categories column remain importable, with a maximum of three categories.

The Excel template hides and prefills Service template. Questions use Label as their identifier, inline Choices (one label per line; saved values equal labels), and Show if label / Operation / Value conditions. Separate Choices, Table rows, and Conditions sheets are no longer generated. Tables, repeatable groups, and advanced settings are excluded from new templates. Older workbook formats remain importable.

Inline conditions support text and single-choice operations is, is not, contains, does not contain, starts with, and ends with. Multi-select conditions support includes and does not include. Value accepts a choice label, free text, or (no value); blank also means no value when a condition is present. Choice labels export as QUESTION_OPTION, free text as STRING, and no value as null. The Operation dropdown lists all eight operations; import validates the chosen operation against the referenced question type. The Value dropdown includes (no value) and the referenced question’s choice labels, and also permits free text.


The **Workflow** tab is an ordered approval list with Service name, Approval type, Approval summary, and Approvers. Choose Line manager approval or Custom Approval; enter Approvers for custom approval (mapped to the reference Flex Char 01 input). The filled sample runs line manager approval followed by custom approval. Variables, QAnswer, Start, End, connections, and conditions are generated automatically.

Every service runs Start → QAnswer → approvals in row order → End, even if no approval rows are provided. After each approval, a gateway checks that approval's own Status: Approved continues; any other status sets the service request to Rejected and ends it on a separate rejection End node. The approved path has its own final End node. Context and question variables use PascalCase with English letters only. QAnswer's custom called process is included in the package. Older advanced Workflow sheets remain importable, with QAnswer moved immediately after Start. Editing an imported service in the web builder preserves its workflow.
