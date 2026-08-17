---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - docs/planning/prd.md
  - docs/planning/prd-addendum.md
  - docs/planning/architecture.md
  - docs/planning/ARCHITECTURE-SPINE.md
---

# Taiga.io-addons - Epic Breakdown

## Overview

This document decomposes the overlay kit + Components v1 PRD and architecture into implementable stories. No UX spec exists; UI stories follow Taiga chrome and AD-5 (runtime contrib plugin first).

## Requirements Inventory

### Functional Requirements

- FR-1: Drop-in overlay — operator applies overlay without editing official `docker-compose.yml`
- FR-2: Official images as immutable base — overlay `FROM` pinned official tags; never `:latest`
- FR-3: Addon load without Taiga source edits — Django `INSTALLED_APPS` + front `contribPlugins`
- FR-4: Documented Upgrade playbook
- FR-5: Overlay removal is safe for Official Taiga (Addon-owned schema)
- FR-6: Create Component (unique per Project, case-insensitive)
- FR-7: Rename Component (updates assignments and chips)
- FR-8: Delete Component (unlink assignments; do not delete User Stories)
- FR-9: List and reorder catalog (Project-scoped)
- FR-10: Catalog write = project admin; read = project member
- FR-11: Assign 0–N Components from that Project catalog
- FR-12: Persist and reload Assignment
- FR-13: Assignment write = story editor; reject cross-project ids
- FR-14: Story-detail picker in Taiga UI
- FR-15: Chips on kanban and backlog cards

### NonFunctional Requirements

- NFR-1: Upgrade friction is pin → rebuild → migrate Addon apps → smoke-test (no Taiga source merge)
- NFR-2: Official env-generated `config.py` / `conf.json` must keep working (append, never replace)
- NFR-3: Auth is Official Taiga JWT; no second identity system
- NFR-4: Overlay must not break Official Taiga if Addon containers are removed
- NFR-5: Addon UI in English, matching Taiga chrome
- NFR-6: Official `taiga-back` and `taiga-async` stay on the **same** overlay image

### Additional Requirements

- Overlay-not-fork paradigm (AD-1)
- Pin seed `6.10.2`; operator production tag wins (AD-2)
- Entrypoint wrappers append `INSTALLED_APPS` and `contribPlugins` (AD-3)
- Override `taiga-back` **and** `taiga-async` (AD-4)
- Runtime contrib plugin first; isolated front-from-source rebuild is documented fallback only (AD-5)
- Schema: `Component` + `Assignment` only; FKs to Official Taiga PKs (AD-6)
- Permissions map to existing Taiga roles (AD-7)
- REST under `/api/v1/components/...` (AD-8)
- One Addon = `addons/<slug>/{back,front}` + `platform/addons.txt` (AD-9)
- Official back entrypoint already runs `migrate` — Addon apps migrate on boot
- Front plugin path in Docker: `/usr/share/nginx/html/plugins/<slug>/`

### UX Design Requirements

None. No UX spec. Stories use Official Taiga settings / story-detail / card patterns.

### FR Coverage Map

| FR | Stories |
| --- | --- |
| FR-1 | 1.1 |
| FR-2 | 1.1 |
| FR-3 | 1.1, 1.2, 3.1 |
| FR-4 | 1.3 |
| FR-5 | 1.1, 2.1 |
| FR-6 | 2.2, 3.1 |
| FR-7 | 2.2, 3.1 |
| FR-8 | 2.2, 3.1 |
| FR-9 | 2.2, 3.1 |
| FR-10 | 2.2, 3.1 |
| FR-11 | 2.3, 3.2 |
| FR-12 | 2.3, 3.2 |
| FR-13 | 2.3 |
| FR-14 | 3.2 |
| FR-15 | 3.3 |
| NFR-1–6 | 1.1–1.3 |

## Epic List

1. **Overlay platform** — Operator can attach this repo to official `taiga-docker` and upgrade by bumping pins.
2. **Components backend** — Catalog and Assignment exist as Addon-owned API with Taiga permissions.
3. **Components frontend** — Project admin maintains the catalog; story editors assign; boards show chips.

---

## Epic 1: Overlay platform

Prove the upgrade-safe attach path with a **loadable empty Addon** before any Components domain logic. After this epic, official compose is untouched, overlay images boot, and a no-op plugin is visible to Taiga.

### Story 1.1: Overlay scaffolding

As an operator,
I want Dockerfiles and a compose override that swap official back/async/front for images built `FROM` a pinned official tag,
So that I can attach this repo to production without forking `taiga-docker`.

**Acceptance Criteria:**

**Given** an official `taiga-docker` directory
**When** I copy `platform/docker-compose.override.yml` beside it and build/start
**Then** `taiga-back` and `taiga-async` use the overlay back image and `taiga-front` uses the overlay front image
**And** official `docker-compose.yml` is not modified
**And** Dockerfiles `FROM taigaio/taiga-back:<pin>` and `taigaio/taiga-front:<pin>` (no `:latest`)
**And** the pin is a single declared value (seed `6.10.2`, overridable)

**Given** the overlay images
**When** the stack is healthy
**Then** I can log into Taiga as before (gateway, db, events unchanged)

### Story 1.2: Plugin load without replacing official config

As an operator,
I want Addon Django apps and front plugins appended to official generated config,
So that my existing `.env` URLs and flags keep working.

**Acceptance Criteria:**

**Given** official back config generated from env
**When** the overlay back container starts
**Then** `INSTALLED_APPS` includes each slug from `platform/addons.txt` as `taiga_contrib_<slug>`
**And** official env-driven settings (domain, secret, email, etc.) are still in effect

**Given** official front `conf.json` generated from env
**When** the overlay front container starts
**Then** `contribPlugins` includes `plugins/<slug>/<slug>.json` for each enabled slug
**And** official `api` / `eventsUrl` / `baseHref` are unchanged

**Given** a stub `addons/components` back app and front plugin (no domain logic required)
**When** I inspect running containers
**Then** the stub app is importable and the stub plugin files exist under `/usr/share/nginx/html/plugins/components/`

### Story 1.3: Upgrade playbook and smoke test

As an operator,
I want a written Upgrade playbook plus a smoke checklist,
So that bumping Official Taiga is a rehearsal, not an invention.

**Acceptance Criteria:**

**Given** `platform/UPGRADE.md`
**When** I read it
**Then** it lists: backup DB → pull official compose updates → bump pin → rebuild overlay → `up -d` → Addon migrate via official entrypoint → smoke catalog/picker/chips (or stub load until those exist)
**And** it states core Taiga migrations are Official Taiga’s
**And** it documents AD-5 fallback (front-from-source rebuild) as non-default

**Given** a smoke script or documented curl/UI checks
**When** I run them against a healthy overlay
**Then** they fail if the stub Addon back app is missing from `INSTALLED_APPS` or the front plugin JSON is missing from `contribPlugins`

---

## Epic 2: Components backend

Persist the Component catalog and User Story Assignments in Addon tables, exposed as authenticated REST that reuses Taiga permissions.

### Story 2.1: Models and migrations

As a developer,
I want Addon models for Component and Assignment with FKs to Official Taiga,
So that data survives upgrades and overlay removal does not break core tables.

**Acceptance Criteria:**

**Given** the overlay back image with `taiga_contrib_components` installed
**When** the container boots (official `migrate`)
**Then** Addon tables exist for Component (`project_id`, `name`, `order`) and Assignment (`userstory_id`, `component_id`)
**And** no migration alters Official Taiga tables
**And** `(project_id, lower(name))` is unique
**And** `(userstory_id, component_id)` is unique
**And** deleting a Component deletes its Assignment rows only

### Story 2.2: Catalog REST and permissions

As a project admin,
I want to create, list, reorder, rename, and delete Components via API,
So that the catalog is the only source of names for that Project.

**Acceptance Criteria:**

**Given** I am a project admin
**When** I POST/PATCH/DELETE/reorder on `/api/v1/components/` for my Project
**Then** the catalog updates and uniqueness (trimmed, case-insensitive) is enforced
**And** another Project never sees these Components

**Given** I am a project member but not admin
**When** I GET the catalog
**Then** I receive the list
**And** write operations return 403

**Given** I am unauthenticated
**When** I call catalog endpoints
**Then** I receive 401

**Given** a Component with Assignments
**When** an admin deletes it
**Then** Assignment rows are removed and User Stories remain

### Story 2.3: Assignment REST and permissions

As a story editor,
I want to set 0–N Component ids on a User Story,
So that the Assignment persists and reloads.

**Acceptance Criteria:**

**Given** a User Story and that Project’s catalog
**When** a story editor PUT/PATCHes the Assignment set (including empty)
**Then** GET returns the same set with current names
**And** duplicate ids are ignored or rejected as a no-op uniqueness

**Given** a Component id from another Project
**When** I try to assign it
**Then** the API rejects the write

**Given** I can view but not edit the User Story
**When** I GET Assignment
**Then** I succeed
**And** write returns 403

---

## Epic 3: Components frontend

Surface catalog, picker, and chips inside Official Taiga via the contrib plugin.

### Story 3.1: Project settings catalog UI

As a project admin,
I want a Components section in Project settings,
So that I can maintain the catalog without leaving Taiga.

**Acceptance Criteria:**

**Given** I am a project admin
**When** I open Project settings
**Then** I can add, rename, reorder, and delete Component names
**And** delete of a name that is assigned asks for confirmation
**And** validation errors (empty / duplicate) are shown

**Given** I am not a project admin
**When** I open Project settings
**Then** I do not get catalog write controls

### Story 3.2: User Story detail picker

As a story editor,
I want to pick 0–N Components on the User Story detail,
So that Assignment is visible and editable in the same place I edit the story.

**Acceptance Criteria:**

**Given** I can edit the User Story
**When** I open its detail
**Then** I see a multi-select of the Project catalog with current Assignment selected
**And** saving persists via the Assignment API
**And** reload shows the same set

**Given** I can only view the User Story
**When** I open its detail
**Then** I see assigned names read-only

**Given** the catalog is empty
**When** I open the detail
**Then** the picker is empty / explains that the admin must define Components

### Story 3.3: Kanban and backlog chips

As a project member,
I want assigned Component names on kanban and backlog cards,
So that I can scan ownership without opening the story.

**Acceptance Criteria:**

**Given** a User Story with Assignments
**When** I view kanban or backlog
**Then** the card shows chips with current Component names in catalog order
**And** a story with zero Assignments shows no chips

**Given** a Component is renamed
**When** I refresh the board
**Then** chips show the new name

**Given** the pinned front tag cannot host the injection
**When** the implementer hits that wall
**Then** they follow AD-5 fallback (documented isolated rebuild) rather than forking front in place
**And** they record the fallback in `platform/UPGRADE.md`
