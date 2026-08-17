---
title: Taiga Addons overlay kit + Components v1
status: final
created: 2026-08-17
updated: 2026-08-17
---

# PRD: Taiga Addons overlay kit + Components v1

## 0. Document Purpose

This PRD is for the operator of a self-hosted Taiga 6 production instance (Forza) and for downstream architecture, epics, and story work. It states what the overlay kit and the first addon must do, not how they are built. Technical mechanism lives in `addendum.md` and the architecture spine. Vocabulary is locked in the Glossary; `[ASSUMPTION]` tags are indexed in §9.

## 1. Vision

Self-hosted Taiga already runs production work. The product is not a new project manager — it is a **durable way to add backend and frontend capabilities** to official Taiga Docker without forking the product and without making the next Taiga upgrade a rewrite.

The first capability is **Components**: a project-owned list of names, attached 0-to-N on each User Story, visible on the story detail and on kanban and backlog cards. That is the Jira-style “this story belongs to these parts of the system” cut, kept deliberately thin so the overlay contract is proven on a real, useful feature.

Success is measured in two layers: the operator can upgrade official Taiga with a short, repeatable playbook; the project team can maintain and use Components without leaving Taiga.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional (operator):** Add capabilities to production Taiga without owning a fork of `taiga-back`, `taiga-front`, or `taiga-docker`.
- **Functional (operator):** Upgrade official Taiga later with bounded, rehearsed friction — bump pinned tags, rebuild overlays, migrate addon tables only, smoke-test.
- **Functional (project admin):** Define the Component catalog for a Project so the team shares one list of names.
- **Functional (story worker):** Tag a User Story with the relevant Components, and see those names on the board without opening the story.
- **Contextual:** Production is official self-hosted Docker (`taigaio/taiga-docker`). This repo is an overlay kit dropped next to that compose, not a replacement deploy.

### 2.2 Non-Users (v1)

- Teams on **Taiga Next** / Taiga Cloud.
- Operators who want to patch Taiga core instead of adding isolated addons.
- Users who need Components on tasks, issues, or epics.
- Users who need filter-by-Component, reporting, or Component metadata beyond a name.

### 2.3 Key User Journeys

Internal tooling, single operator plus existing Taiga roles — journeys are one-line scenes, not consumer narratives.

- **UJ-1. Operator overlays addons onto existing Docker.** Forza, with a running official `taiga-docker` stack, copies the overlay compose file beside it, builds images `FROM` the pinned official tags, and brings the stack back up. Taiga still serves the same URL; Components APIs and UI are present. Edge: if the overlay is removed, official Taiga still starts; addon tables remain unused in Postgres.
- **UJ-2. Operator upgrades official Taiga.** Forza pins a newer official tag in this repo, rebuilds overlay images, runs addon migrations, smoke-tests plugin load. Existing Projects, User Stories, and Component assignments survive. Edge: an official breaking change in plugin load is isolated to the overlay Dockerfiles, not a merge conflict in forked Taiga source.
- **UJ-3. Admin defines the catalog.** A project admin opens Project settings, adds/renames/removes Component names. The list is the only source of names the team can attach.
- **UJ-4. Worker assigns Components to a User Story.** A member who can edit the User Story opens it, picks 0–N names from that Project’s catalog, saves. Opening the story later shows the same set.
- **UJ-5. Worker spots Components on the board.** On kanban or backlog, each card shows chips for the assigned Components so the team can scan ownership without opening the story.

## 3. Glossary

- **Addon** — A first-class backend + frontend extension that lives in this repo, has its own schema and UI, and is loaded into official Taiga without modifying Taiga source. Not a Taiga custom attribute and not a tag.
- **Overlay kit** — This repository: Addon source, Dockerfiles that `FROM` official images, a `docker-compose.override.yml` the operator drops next to official `taiga-docker`, and an upgrade playbook.
- **Official Taiga** — Unmodified `taigaio/taiga-docker` compose plus official `taigaio/taiga-back` and `taigaio/taiga-front` images. `[ASSUMPTION: target is Taiga 6 classic (Django + AngularJS), not Taiga Next.]`
- **Pinned tag** — An explicit official image version (never `:latest` in production). Current latest published tag at authoring is `6.10.2`; the operator’s production tag may differ and is the one the overlay must `FROM`.
- **Project** — A Taiga project. The Component catalog is scoped to one Project.
- **Component** — A named item in a Project catalog. v1: name only.
- **Component catalog** — The ordered list of Components that belong to one Project. It is the exclusive set of names that may be assigned to that Project’s User Stories.
- **User Story** — A Taiga user story. v1 assignment target. Not tasks, issues, or epics.
- **Assignment** — The 0–N relationship between one User Story and Components from its Project catalog.
- **Chip** — A compact display of a Component name on a kanban or backlog card.
- **Project admin** — A Taiga member who can administer the Project (settings). `[ASSUMPTION: catalog CRUD is restricted to this role.]`
- **Story editor** — A Taiga member who can edit the User Story. `[ASSUMPTION: Assignment changes require this permission.]`
- **Upgrade playbook** — The documented sequence: bump Pinned tags → rebuild overlay images → run Addon migrations only → smoke-test plugin load.

## 4. Features

### 4.1 Overlay kit (upgrade-safe Addon platform)

**Description:** The operator can attach Addons to Official Taiga through the Overlay kit. Official compose files stay untouched. Overlay images always `FROM` a Pinned tag. Removing the overlay returns the stack to stock Official Taiga. Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-1: Drop-in overlay

The operator can apply the Overlay kit to an existing Official Taiga Docker deploy without editing official `docker-compose.yml`. Realizes UJ-1.

**Consequences (testable):**
- A `docker-compose.override.yml` (or equivalent compose merge) is the only compose file the operator adds beside official `taiga-docker`.
- Official `docker-compose.yml` is not copied, patched, or vendored in this repo.

#### FR-2: Official images as immutable base

Overlay images must be built `FROM` a Pinned tag of official `taiga-back` / `taiga-front`. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- Dockerfiles contain a pinned `FROM taigaio/taiga-back:<tag>` and `FROM taigaio/taiga-front:<tag>`.
- Production compose never references `:latest` for overlay or official app images.

#### FR-3: Addon load without Taiga source edits

Each Addon’s backend and frontend load through Official Taiga’s extension points (installed Django app + front `contribPlugins`), not by patching Taiga source trees. Realizes UJ-1.

**Consequences (testable):**
- This repo contains no clone or fork of `taiga-back` or `taiga-front`.
- If a front hook is missing for Chips or story-detail injection, any unavoidable front-core touch is isolated, documented, and counted as upgrade tax — it is not a silent fork. `[ASSUMPTION: dynamic contribPlugins is attempted first; compile-module rebuild is the fallback.]`

#### FR-4: Documented Upgrade playbook

The operator can follow a written Upgrade playbook to move Official Taiga forward. Realizes UJ-2.

**Consequences (testable):**
- Playbook steps are: pin new official tags → rebuild overlay images → run Addon migrations only → smoke-test that each Addon backend and frontend loaded.
- Playbook states that Official Taiga core migrations remain Official Taiga’s, not this repo’s.

#### FR-5: Overlay removal is safe for Official Taiga

The operator can stop using the overlay and still boot Official Taiga. Realizes UJ-1.

**Consequences (testable):**
- Addon tables live in their own schema/app; they are not columns on Official Taiga core tables.
- After overlay removal, Official Taiga starts and existing Projects / User Stories remain intact.

### 4.2 Component catalog

**Description:** A project admin maintains the Component catalog for a Project: create, rename, reorder, delete names. The catalog is the only source of Component names for that Project. Realizes UJ-3.

**Functional Requirements:**

#### FR-6: Create Component

A project admin can add a Component name to the Project catalog. Realizes UJ-3.

**Consequences (testable):**
- Name is required, trimmed, non-empty.
- Name is unique per Project, case-insensitive. `[ASSUMPTION]`
- New Component appears in the catalog and in the User Story picker for that Project only.

#### FR-7: Rename Component

A project admin can rename a Component. Realizes UJ-3, UJ-5.

**Consequences (testable):**
- The new name replaces the old one everywhere that Component is assigned, including Chips.
- Uniqueness rule of FR-6 still holds.

#### FR-8: Delete Component

A project admin can delete a Component from the catalog. Realizes UJ-3.

**Consequences (testable):**
- The Component disappears from the catalog and from the picker.
- Existing Assignments to that Component are removed; User Stories themselves are not deleted. `[ASSUMPTION: unlink, do not cascade-delete stories.]`

#### FR-9: List and reorder catalog

A project admin can see and reorder the catalog. Realizes UJ-3.

**Consequences (testable):**
- Catalog is Project-scoped; another Project never sees these names.
- Display order is the order the picker and (if relevant) chips follow unless a later FR says otherwise. `[ASSUMPTION: chips follow catalog order.]`

#### FR-10: Catalog permissions

Only a project admin can change the catalog. Realizes UJ-3.

**Consequences (testable):**
- Non-admin members can read the catalog (needed for the picker) but create/rename/reorder/delete return forbidden.
- Unauthenticated requests are rejected.

### 4.3 User Story Assignment

**Description:** A story editor attaches 0–N Components from the current Project catalog to a User Story, and sees that set on the story detail. Realizes UJ-4.

**Functional Requirements:**

#### FR-11: Assign 0–N Components

A story editor can set the Assignment of a User Story to any subset of the Project catalog, including none. Realizes UJ-4.

**Consequences (testable):**
- Picker offers only that Project’s current catalog.
- Duplicate Assignment of the same Component is impossible.
- Saving an empty set is valid.

#### FR-12: Persist and reload Assignment

Opening the User Story later shows the last saved Assignment. Realizes UJ-4.

**Consequences (testable):**
- GET of the User Story (or the Addon’s assignment resource) returns the assigned Component ids and names.
- A Component deleted after Assignment no longer appears (FR-8).

#### FR-13: Assignment permissions

Only a story editor can change Assignment. Realizes UJ-4.

**Consequences (testable):**
- Viewers can read Assignment; they cannot change it.
- Cross-project Component ids are rejected.

#### FR-14: Story-detail picker

The User Story detail UI exposes the picker without leaving Taiga. Realizes UJ-4.

**Consequences (testable):**
- The control is on the User Story detail surface (not a separate admin-only page).
- It lists catalog names and current Assignment.

### 4.4 Card Chips

**Description:** Kanban and backlog cards show Chips for assigned Components so the board can be scanned. Realizes UJ-5.

**Functional Requirements:**

#### FR-15: Chips on kanban and backlog

Anyone who can view the board sees Chips for assigned Components on each User Story card. Realizes UJ-5.

**Consequences (testable):**
- Kanban card and backlog card both show the assigned names.
- A story with zero Assignments shows no Chips (no empty placeholder required).
- Chip text is the current Component name (tracks rename).

**Out of Scope:**
- Filter, search, or group-by Component.
- Chips on task/issue/epic cards.

## 5. Non-Goals (Explicit)

- Fork or vendor Official Taiga source or official `docker-compose.yml`.
- Target Taiga Next or Taiga Cloud.
- Replace Taiga tags or custom attributes; Components is a separate Addon.
- Filter-by-Component, swimlanes-by-Component, or reporting.
- Component fields beyond name (color, owner, description).
- Components on tasks, issues, or epics.
- Public marketplace / multi-tenant Addon store.
- Changing Official Taiga’s auth, permissions model, or theming.

## 6. MVP Scope

### 6.1 In Scope

- Overlay kit: Dockerfiles `FROM` Pinned tags, compose override, plugin-load contract, Upgrade playbook, smoke test.
- Component catalog CRUD (name only) at Project settings.
- 0–N Assignment on User Story detail.
- Chips on kanban and backlog cards.
- Addon-owned persistence and REST; Official Taiga core schema untouched.

### 6.2 Out of Scope for MVP

- Filter-by-Component (deferred; would touch Official Taiga filter UI).
- Extra Component metadata (deferred until catalog is used).
- Other work-item types (deferred; same data model can extend later).
- Theming / i18n beyond English v1.

## 7. Success Metrics

Internal operator tool — qualitative is enough.

**Primary**
- **SM-1**: Operator completes an Official Taiga upgrade using only the Upgrade playbook, with Components still loaded and Assignments intact. Validates FR-2, FR-4, FR-12.
- **SM-2**: A project admin can define a catalog and a story editor can assign and see Chips in the same session. Validates FR-6, FR-11, FR-15.

**Counter-metrics (do not optimize)**
- **SM-C1**: Number of files copied out of official `taiga-back` / `taiga-front`. Must stay at zero (or a documented, isolated hook if FR-3 fallback fires). Counterbalances “just patch core, it’s faster.”

## 8. Open Questions

1. What Pinned tag is running in production today? Overlay seed uses `6.10.2` (current official `latest`); the operator’s tag wins.
2. If Official Taiga exposes no card/detail hook, does the operator accept a thin front rebuild (upgrade tax) rather than dropping Chips from v1? Chips are in-scope, so the fallback is allowed.
3. Should catalog delete require a confirm when Assignments exist? `[ASSUMPTION: yes, confirm in UI; API may still delete+unlink.]`

## 9. Assumptions Index

- Target is Taiga 6 classic on official `taigaio/taiga-docker`, not Taiga Next. — §3, §5
- Catalog CRUD is project-admin; read is any project member. — FR-10
- Assignment changes require story-edit permission; view is any viewer. — FR-13
- Names unique per Project, case-insensitive, trimmed. — FR-6
- Delete Component unlinks Assignments; does not delete User Stories. — FR-8
- Chips follow catalog order. — FR-9
- Addon UI in English, matching Taiga chrome as closely as practical. — §6.2
- Dynamic `contribPlugins` first; isolated front compile-module rebuild only if hooks cannot paint the picker or Chips. — FR-3
- Delete-with-assignments shows a UI confirm. — §8.3
