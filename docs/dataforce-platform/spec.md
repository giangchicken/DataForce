# DataForce — Collaborative Data Annotation Platform (v1)

## What

DataForce is a self-hosted, collaborative platform where teams import raw data, label it against a declarative project schema, review each other's work, and export immutable, versioned snapshots in training-ready formats. v1 covers **text** (classification, NER spans, free text) and **image** (classification, bounding box, polygon) across a shared task/annotation/review pipeline, with multi-annotator overlap, inter-annotator agreement scoring, ground-truth honeypots, and COCO/YOLO/JSONL/CSV export. Contributors get work two ways: they **browse a catalog** of datasets open to them and opt in, or they **subscribe** and receive a continuous feed. It ships as a Docker Compose deployment with an Organization → Workspace → Project hierarchy and role-based access control.

This is one of three specs. [`agent-toolkit`](../agent-toolkit/spec.md) is the shared Python library DataForce depends on for LLM access and JSON/file utilities, built in its own repository. [`guided-validation`](../guided-validation/spec.md) is the presentation mode that serves LLM-generated questions one at a time for dataset review, built on the task and review machinery specified here. Build order is agent-toolkit → platform → guided-validation.

## Context

There is no existing code — this repository is empty and this spec defines the initial build. Two internal codebases were surveyed and shape it: the `agent-evaluation` service supplies the LLM client and utilities being extracted into [`agent-toolkit`](../agent-toolkit/spec.md), and the Tool-Decision-Model training set (`fc_train_final.json`) is the first real dataset to be validated here, driving the streaming-import and adapter requirements and specified in [`guided-validation`](../guided-validation/spec.md).

The design borrows deliberately from platforms that have already proven these mechanics at scale, rather than inventing:

- **Label Studio** ([repo](https://github.com/HumanSignal/label-studio), [task format](https://labelstud.io/guide/task_format)) — the Task / Annotation / Prediction data model, the `result` array of region objects with normalized percentage coordinates, and the ML-backend integration contract. Its monorepo splits a Django backend from a React editor. We adopt its data shapes and reject its XML labeling config (see Decisions).
- **CVAT** ([repo](https://github.com/cvat-ai/cvat), [auto QA docs](https://docs.cvat.ai/docs/qa-analytics/auto-qa/)) — the job stage model (annotation → validation → acceptance) and the **honeypot** pattern: a small ground-truth set annotated once, then invisibly injected into normal annotation jobs so annotator accuracy is measured continuously against a validation set far smaller than full re-annotation.
- **Label Studio Enterprise task reservation** ([project settings](https://docs.humansignal.com/guide/project_settings_lse)) — tasks are reserved when an annotator opens them and released on submit or expiry; reservations respect the configured overlap. Its documented failure mode (annotators cherry-picking tasks leave large numbers locked; two browser tabs circumvent overlap) directly motivates our lock TTL, reaper job, and server-side duplicate-annotation constraint.
- **Doccano / Argilla** — text-only tools; Doccano is noted for weak collaboration features, which is precisely the gap DataForce targets.
- **Agreement literature** ([Label Studio IAA tutorial](https://labelstud.io/tutorials/how_to_measure_inter_annotator_agreement_and_build_human_consensus), [Encord](https://encord.com/blog/achieving-annotation-consensus-strategies-for-high-agreement-datasets/)) — Cohen's kappa for annotator pairs, Fleiss' kappa for >2 annotators on complete designs, and Krippendorff's alpha when annotators do **not** all label everything. Overlap assignment produces exactly that incomplete design, so alpha is the project-level default.

The strategic claim behind the product — that consensus strength is a usable confidence signal, and that reviewing contentious tasks beats reviewing all tasks — is what the quality subsystem is built to deliver.

## Requirements

### Identity, tenancy, access

1. A user authenticates with email + password and receives a short-lived access token plus a rotating refresh token; a user may also create named personal access tokens for SDK/CI use.
2. Every persisted row outside the `users` table is scoped to exactly one organization, and every query path filters by the caller's organization.
3. Org roles are `owner`, `admin`, `member`. Project roles are `manager`, `reviewer`, `annotator`. A user's effective permission on a project is the union of their org role and project role.
4. An `annotator` can read only the tasks assigned or served to them and only their own annotations; they must not see other annotators' results for the same task while that task is open for annotation.
5. Every state-changing action writes an immutable audit record (actor, entity, action, before/after diff, timestamp).

### Projects and schemas

6. A project declares a **label schema**: a versioned JSON document naming its inputs (which fields of a task's data are displayed, and how) and its controls (what may be annotated, with which labels, and whether required).
7. v1 supports control types `choice`, `span`, `bbox`, `polygon`, `text`, and `rating`. `span` applies only to text inputs; `bbox` and `polygon` only to image inputs; the rest to both.
8. The server validates every submitted annotation against the project's label schema and rejects non-conforming results with a field-level error.
9. Editing a label schema creates a new schema version. Existing annotations remain bound to the version they were created under. Removing or renaming a label that is in use requires an explicit migration action and is refused otherwise.
10. A project declares `annotations_per_task` (overlap, default 1), `review_required` (default true), and `lock_ttl_seconds` (default 1800).

### Data import and storage

11. Tasks are created by direct JSON/CSV/JSONL upload, by presigned file upload, or by syncing a prefix in an S3-compatible bucket. Each import names a **dataset adapter** that maps the source format into tasks; v1 ships `generic_json`, `jsonl`, `csv`, and `coco`, and the adapter interface is the extension point for domain formats (the `fc_tool_decision` adapter is specified in [guided-validation](../guided-validation/spec.md)). Adapters stream their input via `agent_toolkit.file_utils.iter_json_array_file` rather than loading it whole, so a 100MB+ source file imports in bounded memory.
12. Media is never streamed through the API for bulk read; clients receive short-TTL presigned URLs.
13. Import is idempotent on a caller-supplied `external_id` within a project: re-importing the same `external_id` updates the task's data and never duplicates it or orphans its annotations.

### Annotation flow

14. `POST /projects/{id}/next-task` atomically selects one eligible task, reserves it for the caller, and returns it with the schema, any predictions, and the caller's existing draft if one exists.
15. A task is eligible for a caller when: it is not `accepted`; its submitted annotation count plus its live reservation count is below `annotations_per_task`; the caller has no submitted annotation on it; and the caller holds no other live reservation on it.
16. Concurrent `next-task` calls must never over-serve a task beyond `annotations_per_task`, and no annotator may hold two annotations on one task.
17. A reservation expires after `lock_ttl_seconds`; a heartbeat extends it; submitting or skipping releases it. Expired reservations are reclaimed by a scheduled reaper.
18. Annotators may save drafts (not counted toward overlap), submit, or skip with a reason.
19. Submitting an annotation records `lead_time_ms` measured server-side from reservation to submission.

### Review and consensus

20. When `review_required`, submitted annotations enter a review queue visible to `reviewer` and `manager` roles. A reviewer may not review their own annotation.
21. A reviewer verdict is `accepted`, `rejected` (requires a reason), or `amended` (reviewer supplies a corrected result, stored as a new annotation attributed to the reviewer with `origin = review_amend`, leaving the original intact).
22. A rejected annotation returns its task to the annotation pool with the rejection comment attached, routed back to the original annotator when they are still an active project member and to the general pool otherwise.
23. When `annotations_per_task > 1`, reaching the required submission count triggers agreement computation for that task. Tasks scoring below the project's `agreement_threshold` are flagged `conflict` and surfaced at the top of the review queue.
24. A task becomes `accepted` only when it holds at least one accepted annotation, and never automatically in v1.

### Quality

25. Tasks may be flagged as ground truth. Ground-truth tasks are excluded from normal export and are injected into annotator queues at a configurable rate (default 5%) without any visual marking.
26. The platform computes and stores: per-task agreement, per-project Krippendorff's alpha per `choice` control, per-annotator ground-truth accuracy, and per-annotator throughput and rejection rate.
27. Agreement between two results is computed per control type: exact match for `choice` and `rating`; span-level F1 for `span`; greedy IoU matching at threshold 0.5 for `bbox` and `polygon`; normalized edit distance for `text`.

### Predictions

28. A project may register an ML backend URL. DataForce calls its `/predict` endpoint with tasks and stores returned results as predictions with a `model_version` and `score`.
29. Predictions are shown to annotators as a pre-filled starting point and are never counted as annotations. Whether an annotation started from a prediction is recorded.

### Export

30. Export is asynchronous, produces an immutable snapshot in object storage, and records a `dataset_version` row with format, applied filters, item count, and SHA-256 of the artifact.
31. v1 export formats: DataForce JSON (lossless native), JSONL, CSV, COCO (bbox + polygon), YOLO (bbox).
32. Export defaults to accepted annotations only; the filter is explicit in the recorded snapshot so any export is reproducible.

### Collaboration

33. Users may comment on a task or an annotation, in threads, with `@mention` of any project member.
34. Each project exposes an activity feed derived from the audit log.

### Finding work

35. A project may be listed in the organization's **dataset catalog**, which any org member can browse. A catalog entry shows the project's purpose, modality, presentation mode, task volume, remaining work, required skills, and current progress — enough to decide without joining.
36. Catalog visibility is `open` (any org member may join themselves as an annotator), `request` (joining creates a request a manager approves or declines), or `hidden` (invitation only, the default). Visibility is independent of project role: browsing a catalog entry never grants access to its tasks.
37. A user may **subscribe** to a catalog project, optionally narrowed by a saved filter, and receives work from it continuously without re-selecting it.
38. `POST /api/v1/next-task` with no project supplied draws from the caller's active subscriptions, honoring per-subscription priority and a daily cap when set.
39. A subscription may be paused, resumed, or dropped by its owner at any time; pausing releases nothing already reserved and takes effect on the next request.
40. Subscription and catalog membership never bypass the eligibility rules in requirement 15. Everything a subscription changes is *which pool* is drawn from, not *how* a task is served.
41. A project may declare a **presentation mode**: `form` (the schema-driven labeling UI, the default) or `guided` (one LLM-generated question at a time, per [guided-validation](../guided-validation/spec.md)). Mode changes what the annotator sees; it does not change the task, annotation, review, or export model.

## Design

### Repository layout

```
dataforce/
├── apps/
│   ├── api/                       FastAPI service
│   │   ├── dataforce_api/
│   │   │   ├── core/              config, db session, security, dependencies, errors
│   │   │   ├── schema/            label-schema models + result validators (shared vocabulary)
│   │   │   ├── modules/
│   │   │   │   ├── orgs/          organizations, workspaces, memberships
│   │   │   │   ├── auth/          login, tokens, PATs
│   │   │   │   ├── projects/      projects, label schema versions, settings
│   │   │   │   ├── catalog/       catalog listing, join requests, subscriptions
│   │   │   │   ├── adapters/      DatasetAdapter protocol + built-in adapters
│   │   │   │   ├── tasks/         import, storage sync, reservation, next-task
│   │   │   │   ├── annotations/   drafts, submit, skip
│   │   │   │   ├── reviews/       review queue, verdicts
│   │   │   │   ├── quality/       agreement metrics, honeypots, annotator scores
│   │   │   │   ├── exports/       snapshot jobs, format converters
│   │   │   │   ├── ml/            ML backend registry, prediction ingestion
│   │   │   │   └── activity/      audit log, comments, feed
│   │   │   ├── workers/           celery app, scheduled jobs (reaper, metrics, exports)
│   │   │   └── migrations/        alembic
│   │   └── tests/
│   ├── web/                       React 19 + Vite + TypeScript
│   │   └── src/
│   │       ├── api/               generated OpenAPI client + TanStack Query hooks
│   │       ├── features/
│   │       │   ├── projects/  dashboard/  review/  quality/
│   │       │   ├── catalog/       browse, join, subscription management
│   │       │   └── labeling/
│   │       │       ├── engine/    schema→UI renderer, result state, hotkeys
│   │       │       └── controls/  choice, span, bbox, polygon, text, rating
│   │       └── components/        design-system primitives
│   └── packages/sdk-python/       dataforce client + MLBackend base class
├── deploy/                        docker-compose.yml, Dockerfiles, .env.example
└── docs/
```

Each API module holds `router.py` (HTTP + auth), `service.py` (business rules, transactions), `repository.py` (SQLAlchemy queries), `models.py` (ORM), `schemas.py` (Pydantic I/O). Routers never touch the ORM; services own transaction boundaries. This is the pattern for the whole codebase — new modules follow it.

### Data model

Postgres, all IDs are UUIDv7 (time-sortable, index-friendly), all timestamps `timestamptz`.

```
organization(id, name, slug*, created_at)
user(id, email*, password_hash, full_name, is_active, created_at)
membership(id, org_id→, user_id→, role, UNIQUE(org_id,user_id))
workspace(id, org_id→, name, created_at)

project(id, org_id→, workspace_id→, name, modality, status,
        active_schema_version_id→, annotations_per_task, review_required,
        agreement_threshold, honeypot_rate, lock_ttl_seconds,
        presentation_mode, catalog_visibility, catalog_summary, required_skills TEXT[],
        created_at)
subscription(id, user_id→, project_id→, saved_filter JSONB, priority,
             daily_cap, is_paused, created_at, UNIQUE(user_id, project_id))
join_request(id, project_id→, user_id→, status, decided_by→, decided_at, created_at,
             UNIQUE(project_id, user_id))
import_run(id, project_id→, adapter, source_uri, source_sha256, requested,
           created, updated, skipped, unparsed, status, error,
           started_at, finished_at)
label_schema_version(id, project_id→, version, definition JSONB, created_by→, created_at,
                     UNIQUE(project_id, version))
project_member(id, project_id→, user_id→, role, UNIQUE(project_id,user_id))

task(id, org_id→, project_id→, external_id, data JSONB, meta JSONB,
     is_ground_truth, status, submitted_count, accepted_count,
     agreement_score, created_at, UNIQUE(project_id, external_id))
task_reservation(id, task_id→, user_id→, acquired_at, expires_at, released_at)
prediction(id, task_id→, model_version, result JSONB, score, created_at)

annotation(id, org_id→, project_id→, task_id→, author_id→, schema_version_id→,
           result JSONB, status, origin, from_prediction, skip_reason,
           lead_time_ms, created_at, updated_at)
review(id, annotation_id→, reviewer_id→, verdict, comment,
       amended_annotation_id→, created_at)

annotator_score(id, project_id→, user_id→, gt_accuracy, submitted, rejected,
                avg_lead_time_ms, computed_at, UNIQUE(project_id,user_id))
dataset_version(id, project_id→, version, format, filters JSONB, item_count,
                artifact_uri, sha256, created_by→, created_at,
                UNIQUE(project_id, version))

comment(id, org_id→, entity_type, entity_id, parent_id→, author_id→, body, created_at)
audit_log(id, org_id→, actor_id→, entity_type, entity_id, action, diff JSONB, created_at)
ml_backend(id, project_id→, url, auth_header_encrypted, is_active, created_at)
storage_connection(id, project_id→, kind, bucket, prefix, credentials_encrypted, last_synced_at)
webhook(id, project_id→, url, events TEXT[], secret_encrypted, is_active)
```

Enums: `task.status ∈ {pending, in_progress, annotated, in_review, conflict, accepted}`; `annotation.status ∈ {draft, submitted, skipped, superseded}`; `annotation.origin ∈ {human, review_amend}`; `review.verdict ∈ {accepted, rejected, amended}`; `project.presentation_mode ∈ {form, guided}`; `project.catalog_visibility ∈ {open, request, hidden}`; `join_request.status ∈ {pending, approved, declined}`.

Constraints that carry correctness:

```sql
-- one annotator can hold at most one non-draft annotation per task
CREATE UNIQUE INDEX uq_annotation_task_author_active ON annotation (task_id, author_id)
  WHERE status IN ('submitted', 'skipped');

-- one live reservation per (task, user)
CREATE UNIQUE INDEX uq_reservation_live ON task_reservation (task_id, user_id)
  WHERE released_at IS NULL;

-- the hot path for next-task
CREATE INDEX ix_task_queue ON task (project_id, status, id)
  WHERE status IN ('pending', 'in_progress');
```

### Label schema

A schema version's `definition` is a JSON document, validated by Pydantic models in `dataforce_api/schema/`:

```json
{
  "version": 3,
  "modality": "text",
  "inputs": [
    { "name": "content", "type": "text", "source": "$.text" }
  ],
  "controls": [
    { "name": "topic", "type": "choice", "input": "content", "required": true,
      "multiple": false,
      "labels": [{ "value": "billing", "color": "#2563eb", "hotkey": "1" },
                 { "value": "outage",  "color": "#dc2626", "hotkey": "2" }] },
    { "name": "entities", "type": "span", "input": "content", "required": false,
      "allow_overlap": false,
      "labels": [{ "value": "PERSON", "color": "#059669", "hotkey": "p" }] }
  ]
}
```

`source` is a JSONPath into `task.data`, so the same schema shape serves any import layout. Image inputs use `{ "type": "image", "source": "$.image" }` where the value is an object-storage key resolved to a presigned URL at serve time.

### Annotation result

A result is a flat array of regions. Each region names the control that produced it, which keeps validation and agreement computation a per-control operation:

```json
[
  { "id": "01JQ...", "control": "topic", "input": "content", "type": "choice",
    "value": { "labels": ["billing"] } },
  { "id": "01JR...", "control": "entities", "input": "content", "type": "span",
    "value": { "start": 12, "end": 20, "labels": ["PERSON"], "text": "John Doe" } },
  { "id": "01JS...", "control": "defects", "input": "photo", "type": "bbox",
    "value": { "x": 10.5, "y": 20.0, "width": 15.0, "height": 8.0,
               "rotation": 0, "labels": ["scratch"] } }
]
```

Geometry is stored as percentages of the source media's dimensions (Label Studio's convention), so a thumbnail, a re-encode, or a resolution change never invalidates stored annotations. Absolute pixel values are reconstituted at export time from the media dimensions recorded on the task.

### Task distribution

`next-task` runs in one transaction:

```sql
WITH candidate AS (
  SELECT t.id
  FROM task t
  LEFT JOIN LATERAL (
    SELECT count(*) AS live FROM task_reservation r
    WHERE r.task_id = t.id AND r.released_at IS NULL AND r.expires_at > now()
  ) res ON TRUE
  WHERE t.project_id = :project
    AND t.status IN ('pending', 'in_progress')
    AND t.submitted_count + res.live < :annotations_per_task
    AND NOT EXISTS (SELECT 1 FROM annotation a
                    WHERE a.task_id = t.id AND a.author_id = :user
                      AND a.status IN ('submitted','skipped'))
    AND NOT EXISTS (SELECT 1 FROM task_reservation r2
                    WHERE r2.task_id = t.id AND r2.user_id = :user
                      AND r2.released_at IS NULL AND r2.expires_at > now())
  ORDER BY t.id
  FOR UPDATE OF t SKIP LOCKED
  LIMIT 1
)
INSERT INTO task_reservation (task_id, user_id, acquired_at, expires_at)
SELECT id, :user, now(), now() + :ttl FROM candidate
RETURNING task_id;
```

`FOR UPDATE ... SKIP LOCKED` is what makes concurrent callers get *different* tasks instead of blocking or colliding. Honeypot injection happens before this query: with probability `honeypot_rate`, the service instead serves an unserved ground-truth task to this annotator.

Task status transitions, all inside the service layer:

```
pending ──reserve──> in_progress ──submit──> annotated ──(review_required)──> in_review
                          │                       │                              │
                          └──lock expires,        └──(overlap>1, agreement<thr)──> conflict
                             count drops──> pending                               │
                                                                                  ▼
in_review/conflict ──accept/amend──> accepted        ──reject──> pending (re-annotate)
```

### Dataset catalog and subscriptions

The catalog is a filtered view over `project`, not a separate entity: an entry is a project with `catalog_visibility != 'hidden'`, projected down to the summary fields plus live progress counters. Joining an `open` project inserts a `project_member` row with role `annotator`; joining a `request` project inserts a `join_request` a manager resolves.

Subscriptions change only which pool `next-task` draws from. With a project supplied, the query in the previous section runs against that project. Without one, the service walks the caller's unpaused subscriptions in priority order, skipping any that have hit their `daily_cap`, and runs the identical reservation query against the first that yields a task:

```
for sub in active_subscriptions(user) ordered by priority, last_served_at:
    if daily_count(user, sub) >= sub.daily_cap: continue
    task = reserve_next(sub.project_id, user, filter=sub.saved_filter)
    if task: return task
return {"task": null, "reason": "no_subscribed_work"}
```

The eligibility predicate, the `FOR UPDATE SKIP LOCKED`, and the overlap accounting are unchanged — subscriptions are a routing layer over one distribution primitive, not a second one. `last_served_at` on the subscription round-robins between equal-priority subscriptions so one large project cannot starve the rest.

### Dataset adapters

An adapter turns a source file into tasks. The interface is deliberately small:

```python
class DatasetAdapter(Protocol):
    name: str
    def detect(self, sample: bytes) -> bool: ...
    def iter_tasks(self, source: IO[str]) -> Iterator[AdapterTask]: ...

@dataclass
class AdapterTask:
    external_id: str
    data: dict           # matches the project's label schema inputs
    meta: dict           # provenance, carried through untouched
    parse_status: str    # "ok" | "unparsed"
    raw: str | None      # retained when unparsed
```

`iter_tasks` is a generator, so import memory is bounded by one task regardless of file size. The import job consumes it in batches of 1,000 with `INSERT ... ON CONFLICT (project_id, external_id) DO UPDATE`, which is what makes requirement 13's idempotence hold. An `import_run` row accumulates the counts and the source checksum; a source whose checksum differs from a previous run creates a new run rather than silently merging.

A record an adapter cannot parse is imported with `parse_status = "unparsed"` and its raw text retained, never dropped. Silent loss during import is the failure mode that is hardest to notice later — the count looks plausible and nothing errors.

### Quality computation

Agreement runs as a Celery task when a task's `submitted_count` reaches `annotations_per_task`. For each control, all annotator pairs are scored by the control's comparator, the per-control scores are averaged, and the mean lands in `task.agreement_score`. Project-level Krippendorff's alpha per `choice` control is recomputed on a schedule (hourly) rather than per submission, since it is a whole-project statistic and overlap produces an incomplete annotator × task matrix that Fleiss' kappa cannot handle.

Annotator ground-truth accuracy compares each annotator's submission on a honeypot task against the ground-truth annotation using the same comparators.

### API surface

```
POST   /api/v1/auth/login | /refresh | /logout
GET    /api/v1/me
POST   /api/v1/tokens                                personal access tokens

GET    /api/v1/workspaces/{id}/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}                         settings
POST   /api/v1/projects/{id}/schema                  new schema version
GET    /api/v1/projects/{id}/stats                   progress, agreement, throughput

POST   /api/v1/projects/{id}/tasks/import            JSON/CSV/JSONL, idempotent on external_id
POST   /api/v1/projects/{id}/tasks/upload-url        presigned PUT
POST   /api/v1/projects/{id}/storage/sync            S3 prefix sync (async)
GET    /api/v1/projects/{id}/tasks                   filter, sort, paginate

GET    /api/v1/catalog                               browse joinable datasets
GET    /api/v1/catalog/{project_id}                  entry detail + live progress
POST   /api/v1/catalog/{project_id}/join             join (open) or request (request)
GET    /api/v1/projects/{id}/join-requests           manager: pending requests
POST   /api/v1/join-requests/{id}/decide             approve | decline
GET    /api/v1/subscriptions                         mine
POST   /api/v1/subscriptions                         subscribe, optional saved filter
PATCH  /api/v1/subscriptions/{id}                    priority, daily_cap, pause
DELETE /api/v1/subscriptions/{id}

POST   /api/v1/next-task                             draw from my subscriptions
POST   /api/v1/projects/{id}/next-task               reserve + serve from one project
POST   /api/v1/tasks/{id}/heartbeat                  extend reservation
POST   /api/v1/tasks/{id}/annotations                submit | draft | skip
PATCH  /api/v1/annotations/{id}
POST   /api/v1/tasks/{id}/release                    give back a reservation

GET    /api/v1/projects/{id}/review-queue            conflicts first
POST   /api/v1/annotations/{id}/review               accept | reject | amend

POST   /api/v1/projects/{id}/exports                 async → dataset_version
GET    /api/v1/projects/{id}/dataset-versions
GET    /api/v1/dataset-versions/{id}/download        presigned GET

POST   /api/v1/projects/{id}/ml-backends
POST   /api/v1/projects/{id}/predictions/refresh     async batch predict

GET    /api/v1/projects/{id}/activity
POST   /api/v1/comments
```

The React client is generated from the OpenAPI document, so API and UI types cannot drift.

### Permissions

| Action | Annotator | Reviewer | Manager | Org admin |
|---|:--:|:--:|:--:|:--:|
| Serve/annotate tasks | ✓ | ✓ | ✓ | ✓ |
| See others' annotations on an open task | | ✓ | ✓ | ✓ |
| Review annotations (not own) | | ✓ | ✓ | ✓ |
| Edit schema, settings, members | | | ✓ | ✓ |
| Import data, run export | | | ✓ | ✓ |
| See per-annotator quality scores | own only | ✓ | ✓ | ✓ |
| Browse catalog, subscribe | ✓ | ✓ | ✓ | ✓ |
| Set catalog visibility, decide join requests | | | ✓ | ✓ |
| Create projects, manage workspaces | | | | ✓ |

### Deployment

`docker compose up` starts: `api` (uvicorn), `worker` (Celery), `beat` (reaper + metrics schedule), `web` (nginx serving the built SPA and reverse-proxying `/api`), `postgres`, `redis`, `minio`. A single `.env` drives all of it; `make dev` runs API and Vite with hot reload against the same Postgres/Redis/MinIO.

## Decisions

**JSON label schema, not XML.** Label Studio configures projects with an XML tag tree. We use a JSON document validated by Pydantic. *Alternatives:* Label Studio's XML (familiar to migrating users, mature template library); a Python DSL. *Why:* the JSON schema round-trips through Pydantic → OpenAPI → generated TypeScript, so the labeling UI is typed against the same definition the server validates with; XML would need a bespoke parser, a parallel React tag registry, and hand-written types on both sides, and it versions and diffs poorly. *Reversible:* yes for input — an XML→JSON importer can be added for migration — but the internal representation is load-bearing and would be costly to swap.

**Percentage geometry.** Coordinates are stored as percentages of media dimensions rather than absolute pixels. *Alternatives:* absolute pixels (simpler export math, matches COCO directly). *Why:* resolution independence — thumbnails, re-encodes, and CDN transforms don't invalidate stored work; this is Label Studio's choice and it holds up. *Reversible:* yes, via a data migration, provided media dimensions are recorded on the task — so recording them at import is mandatory, not optional.

**Postgres row locks for task distribution, not a queue service.** `SELECT ... FOR UPDATE SKIP LOCKED` plus a reservation table, rather than Redis locks or a dedicated queue. *Alternatives:* Redis `SETNX` locks (fast, but a Redis flush silently loses all reservations and split-brain double-serves); a real queue like SQS (wrong shape — tasks are re-servable, filterable, and long-lived, not messages). *Why:* the reservation must be transactionally consistent with the annotation it guards, and Postgres already holds that data. *Reversible:* yes, behind the repository interface, but there is no reason to.

**No auto-accept on consensus in v1.** Even when N annotators agree perfectly, a human accepts. *Alternatives:* auto-accept above threshold (the throughput win teams actually want). *Why:* v1 must first prove its agreement metrics are trustworthy; auto-accepting on an unvalidated metric silently ships bad labels. The setting is designed for and stubbed as `auto_accept_on_consensus`, defaulting off. *Reversible:* yes — flipping the default is a one-line change once metrics are validated against real projects.

**Celery for background work.** *Alternatives:* arq or Dramatiq (lighter, async-native); FastAPI `BackgroundTasks` (no durability). *Why:* exports and metric recomputation must survive a restart, and `beat` gives scheduled reaping and hourly alpha recomputation without another component. *Reversible:* yes, jobs are thin wrappers over service methods.

**Polling, not WebSockets, for v1.** Queue state, progress, and review counts refresh via TanStack Query. *Alternatives:* SSE or WebSockets for live progress and presence. *Why:* collaboration in v1 is asynchronous by design — reservations, review handoffs, comments — none of which need sub-second propagation; a socket layer is real operational cost (sticky sessions, fan-out, reconnection) for polish. *Reversible:* yes, additive.

**Reviewer amendments create a new annotation.** A reviewer's correction never mutates the annotator's submission; the original is marked `superseded` and retained. *Why:* annotator quality scores are only meaningful if the original work survives; overwriting it destroys the evidence the quality subsystem depends on. *Reversible:* no, in practice — data destroyed by the alternative cannot be recovered.

**Subscriptions route, they do not distribute.** A subscription picks which project pool `next-task` draws from and then runs the same reservation query. *Alternatives:* a per-user materialized work queue, pre-assigning tasks to subscribers. *Why:* a second distribution path is a second place for the over-serving invariant to break, and pre-assignment strands work whenever a subscriber goes inactive — the exact failure Label Studio Enterprise documents for cherry-picking annotators, made permanent. *Reversible:* yes; the routing layer is thin and sits above the primitive.

**A catalog entry is a projection of `project`, not its own entity.** *Alternatives:* a separate `catalog_entry` table a manager publishes to. *Why:* duplicating name, progress, and volume into a second table guarantees they drift; three visibility values on the project carry the same information with no sync problem. *Reversible:* yes.

**Adapters are generators, and unparsable records are imported rather than dropped.** *Alternatives:* parse-then-insert with a validation gate that rejects the file. *Why:* generators are what let a 127MB source import in bounded memory, and an all-or-nothing gate on a heterogeneous real-world file means one malformed record blocks 21,000 good ones. Retaining the raw text makes the failure visible and fixable instead of invisible and permanent. *Reversible:* yes.

**LLM access and JSON/file utilities come from `agent-toolkit`, not from code written here.** *Alternatives:* implement them in DataForce. *Why:* the library exists precisely so this is not rewritten a third time, and its LLM client is already proven against the OpenAI-compatible endpoints this deployment uses. It also means guided validation's generator and any future ML-backend work share one retry, error-mapping, and rate-limiting path. *Reversible:* yes, but choosing otherwise defeats the point of building the library.

**Assumption:** teams run this behind their own network boundary with a trusted user population, so v1 ships password auth plus personal access tokens and defers SSO/SAML/OIDC. The auth module isolates identity resolution behind one interface so an OIDC provider slots in without touching authorization.

**Assumption:** single-node Docker Compose is sufficient for v1 scale — on the order of 10⁶ tasks, tens of concurrent annotators. Nothing in the design blocks horizontal scaling of `api`/`worker` (both are stateless), but no Kubernetes or HA story is specified.

**Assumption:** "multiple annotation tasks" in the product brief means multiple *task types* (classification, NER, detection, …), which is what the control-type system delivers.

## Versions

| Component | Pinned | Source |
|---|---|---|
| Python | 3.14.7 | [python.org, 2026-08-05](https://www.python.org/downloads/release/python-3147/) |
| FastAPI | 0.141.1 | PyPI (checked live) |
| SQLAlchemy | 2.0.52 (async) | PyPI (checked live) |
| Pydantic | 2.13.4 | PyPI (checked live) |
| Alembic | 1.19.1 | PyPI (checked live) |
| Uvicorn | 0.52.3 | PyPI (checked live) |
| Celery | 5.6.3 | PyPI (checked live) |
| agent-toolkit | `>=0.1,<0.2`, extra `[llm]` | [spec](../agent-toolkit/spec.md) — built first; DataForce is its first consumer |
| PostgreSQL | 18.6 | [postgresql.org, 2026-08-13](https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/) |
| Node.js | 24.x LTS | [nodejs/Release](https://github.com/nodejs/Release) — 26 is Current until Oct 2026; stay on LTS |
| React | 19.2.8 | npm (checked live) |
| Vite | 8.2.1 | npm (checked live) |
| TypeScript | 7.0.2 | npm (checked live) |
| TanStack Query | 5.101.4 | npm (checked live) |

PostgreSQL 19 is in beta with a September 2026 target; v1 pins 18.x and revisits after 19.1. Redis and MinIO image tags are pinned to the current stable release at scaffold time — verify then rather than trusting this document.

## Invariants

1. **No over-serving.** For any task, `submitted_count + live_reservations ≤ annotations_per_task`. *Check:* concurrency test firing 32 simultaneous `next-task` calls at a 10-task project with overlap 2, asserting exactly 20 reservations and 12 empty responses.
2. **No double annotation.** No annotator holds more than one `submitted`/`skipped` annotation per task. *Check:* enforced by `uq_annotation_task_author_active`; test asserts the constraint violation surfaces as a 409, not a 500.
3. **Counters match reality.** `task.submitted_count` equals the count of submitted annotations, and `accepted_count` the count of accepted reviews. *Check:* a reconciliation query run in CI after the E2E suite, and available as a `make verify-counters` admin command.
4. **Org isolation.** No API response ever contains a row from another organization. *Check:* a test fixture builds two orgs with identical-shaped data and replays the full endpoint list as org A, asserting zero org-B IDs appear.
5. **Annotations never orphan their schema.** Every annotation references the `label_schema_version` it was authored under, and that version is never deleted. *Check:* FK with `ON DELETE RESTRICT`; test attempts deletion of a referenced version.
6. **Exports are reproducible.** Re-running an export with the same `dataset_version` filters over unchanged data yields an identical SHA-256. *Check:* golden test exporting twice and comparing checksums; requires deterministic ordering and no timestamps inside artifacts.
7. **Subscriptions cannot widen access.** A task served through `POST /next-task` is one the caller would also have been served by that project's own endpoint. *Check:* a test giving a user a subscription to a project they were removed from, asserting the subscribed draw returns nothing.
8. **Import loses no records.** For any `import_run`, `created + updated + skipped + unparsed` equals `requested`. *Check:* a reconciliation assertion at the end of every import job, and a test importing a fixture containing deliberately malformed records.
9. **Ground truth never leaks.** Ground-truth tasks are absent from every non-admin export and are visually indistinguishable in the labeling UI. *Check:* export test asserting exclusion; API contract test asserting the served task payload contains no `is_ground_truth` field.

## Error Behavior

All errors return RFC 9457 `application/problem+json`:

```json
{ "type": "https://dataforce.dev/errors/task-lock-expired",
  "title": "Task reservation expired",
  "status": 409,
  "detail": "Your reservation on this task expired at 2026-08-15T10:31:00Z and it was returned to the pool.",
  "instance": "/api/v1/tasks/01JQ.../annotations",
  "code": "task_lock_expired",
  "errors": [] }
```

| Situation | Status | `code` | Behavior |
|---|---|---|---|
| Reservation expired on submit | 409 | `task_lock_expired` | Submission is **still accepted** if the task remains under its overlap; rejected only if the task filled up meanwhile. The UI warns rather than discarding work. |
| Annotator already annotated task | 409 | `duplicate_annotation` | Returns the existing annotation so the client can switch to edit mode. |
| Result violates schema | 422 | `schema_validation_failed` | `errors[]` carries `{ "pointer": "/2/value/labels/0", "detail": "..." }` per bad region. |
| No eligible task | 200 | — | `{ "task": null, "reason": "queue_empty" \| "all_reserved" \| "no_subscribed_work" \| "daily_cap_reached" }` — an empty queue is not an error. |
| Join a `hidden` project | 404 | — | Deliberately indistinguishable from a nonexistent project; a 403 would confirm it exists. |
| Join a `request` project already requested | 200 | — | Returns the existing pending request. Idempotent, not a conflict. |
| Adapter cannot parse a record | — | — | Imported with `parse_status="unparsed"` and raw text retained; counted in the `import_run`. Never dropped, never fails the run. |
| Source checksum differs from a prior run | 200 | — | Creates a new `import_run` rather than merging into the old one. |
| Reviewer reviews own annotation | 403 | `self_review_forbidden` | |
| Schema edit removes an in-use label | 409 | `label_in_use` | `errors[]` lists affected annotation counts; caller must run an explicit migration. |
| Object storage unreachable | 503 | `storage_unavailable` | `Retry-After` set; import/export jobs retry with exponential backoff, 5 attempts, then land in a failed state with the error preserved on the job. |
| ML backend timeout | — | — | Never fails the annotator's request. Prediction fetch is best-effort with a 10s timeout; the task is served without predictions and the failure is logged to the project's activity feed. |
| Refresh token reuse detected | 401 | `token_reuse_detected` | Entire token family is revoked. |

Losing annotator work is the failure mode that matters most. Drafts autosave to the API every 10 seconds and to `localStorage` on every change; on reconnect the client offers to restore whichever is newer.

## Testing Strategy

**Backend** — pytest against a real PostgreSQL via testcontainers, not SQLite. `SKIP LOCKED`, partial unique indexes, and JSONB operators are all load-bearing and SQLite does not model them.

- Unit: schema validation for every control type (valid, malformed, wrong-input-type); each agreement comparator against hand-computed expected values; Krippendorff's alpha against published worked examples from the IAA literature.
- Concurrency: the invariant-1 test above, plus a lock-expiry race (reaper releases while annotator submits) asserting the documented "accept if still under overlap" behavior.
- Integration: full lifecycle per module — import → serve → submit → review → reject → re-serve → accept → export.
- Export: golden-file tests for each format. COCO and YOLO artifacts are validated by round-tripping through `pycocotools` and the Ultralytics loader respectively, so "our exporter is self-consistent" cannot be mistaken for "the format is correct."
- Property tests (Hypothesis): percentage ↔ absolute coordinate conversion round-trips within float tolerance for arbitrary media dimensions.
- Authorization: parametrized matrix test firing every endpoint as every role, asserting the permission table above cell by cell.

**Frontend** — Vitest + Testing Library for the schema→UI renderer (each control type renders, produces well-formed results, and honors hotkeys), plus the draft-restore logic.

**Catalog and subscriptions** — the invariant-7 access test; round-robin fairness across three equal-priority subscriptions; `daily_cap` enforcement across a day boundary; a paused subscription being skipped without disturbing reservations already held.

**Adapters** — each built-in adapter against a fixture with well-formed, malformed, and duplicate-`external_id` records, asserting the invariant-8 reconciliation and idempotent re-import. A memory-bounded test over a generated 100MB+ source.

**End-to-end** — Playwright against the full compose stack, running the scenario that is the product: a manager creates a project with overlap 2, imports 20 text items and 20 images, publishes it to the catalog, two annotators find it there and subscribe, they label in parallel in separate browser contexts, a reviewer resolves the flagged conflicts, and the manager exports COCO and JSONL and downloads both. This E2E passing is the definition of v1 done.

**Performance smoke** — 100k-task project, asserting `next-task` p95 under 200ms and the task list endpoint under 500ms with filters applied.

## Out of Scope

Deferred to follow-on specs, each of which should be written before it is built:

- **Modalities:** audio, video, time series, PDF/document layout, 3D point cloud.
- **Active learning:** ML-backend `fit()`, retraining webhooks, and uncertainty-based task ordering. v1 ingests predictions only.
- **Auto-accept on consensus**, and reviewer sampling strategies (review only N% of a trusted annotator's work).
- **SSO/SAML/OIDC**, SCIM provisioning, and fine-grained custom roles.
- **Multi-tenant SaaS:** signup, billing, per-tenant isolation beyond the in-app org scoping.
- **Live co-editing and presence.** Task-level reservation is v1's concurrency answer.
- **Kubernetes/Helm deployment**, HA Postgres, and read replicas.
- **Label schema migrations** beyond the explicit refusal in requirement 9 — bulk relabeling tooling is its own project.
- **Annotation instructions/guidelines authoring**, calibration sessions, and annotator training flows, despite the literature identifying these as the highest-leverage quality intervention. They are product surface, not platform plumbing, and v1's agreement metrics are what make them actionable later.
- **Mobile and offline annotation.**
- **Skill-based routing.** `required_skills` is displayed in the catalog and stored; nothing matches on it. Automatic assignment by demonstrated accuracy needs the annotator scores to be validated first.
- **Annotator payment, marketplace, or crowd sourcing.** Subscriptions route work inside one organization; there is no external contributor pool, rate card, or payout.
- **Notifications.** No email or push when subscribed work arrives or a join request is decided; the catalog and queue are pull-only in v1.

Specified separately rather than deferred: [`agent-toolkit`](../agent-toolkit/spec.md) and [`guided-validation`](../guided-validation/spec.md).

---

**Sources consulted:** [Label Studio repo](https://github.com/HumanSignal/label-studio) · [Label Studio task format](https://labelstud.io/guide/task_format) · [Label Studio labeling config](https://labelstud.io/guide/setup) · [Label Studio ML backend](https://labelstud.io/guide/ml_create) · [Label Studio IAA tutorial](https://labelstud.io/tutorials/how_to_measure_inter_annotator_agreement_and_build_human_consensus) · [LSE project settings / task reservation](https://docs.humansignal.com/guide/project_settings_lse) · [LSE quality](https://docs.humansignal.com/guide/quality) · [CVAT repo](https://github.com/cvat-ai/cvat) · [CVAT auto QA & honeypots](https://docs.cvat.ai/docs/qa-analytics/auto-qa/) · [CVAT quality control](https://docs.cvat.ai/docs/qa-analytics/quality-control/) · [CVAT honeypots blog](https://www.cvat.ai/resources/blog/annotation-qa-honeypots) · [Encord: annotation consensus](https://encord.com/blog/achieving-annotation-consensus-strategies-for-high-agreement-datasets/) · [Open-source annotation tools compared](https://www.potatoannotator.com/docs/guides/annotation-tools-compared) · [Roboflow: CV annotation formats](https://roboflow.com/formats)
