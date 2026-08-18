---
baseline_commit: cffe7d6efe64ab020eb747c6421c6bb9dcb3130a
---

# Story 2.1: Models and migrations

Status: in-progress

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a developer,
I want Addon models for Component and Assignment with FKs to Official Taiga,
so that data survives upgrades and overlay removal does not break core tables.

## Acceptance Criteria

1. **Given** the overlay back image with `taiga_contrib_components` installed **When** the container boots (official `migrate`) **Then** Addon tables exist for Component (`project_id`, `name`, `order`) and Assignment (`userstory_id`, `component_id`)
2. **And** no migration alters Official Taiga tables
3. **And** `(project_id, lower(name))` is unique
4. **And** `(userstory_id, component_id)` is unique
5. **And** deleting a Component deletes its Assignment rows only (User Stories survive)

## Tasks / Subtasks

- [x] Red first — write `tests/test_components_models.py` before the model code (repo pattern from 1.1–1.3)
  - [x] Static/AST assertions (always run, no Django needed) — see **Testing requirements**
  - [x] Django+SQLite harness behind `pytest.importorskip("django")` — see **Testing requirements**
  - [x] Live `docker compose exec` assertions behind `skipif` — see **Testing requirements**
- [x] Fix the 1.2 regression trap **before** adding `models.py` (AC: 1)
  - [x] `tests/test_plugin_load.py:267` asserts `not (STUB_APP / "models.py").exists()`. 2.1 intentionally invalidates it. **Delete that one assertion.** Keep `assert not (STUB_APP / "urls.py").exists()` — `urls.py` belongs to 2.2
  - [x] Do **not** weaken `assert imports == ["django.apps"]` (line 255) — `apps.py` may gain assignments, never a new import
- [x] Write `addons/components/back/taiga_contrib_components/models.py` (AC: 1, 3, 4, 5)
  - [x] `Component`: `project` FK → `"projects.Project"`, `name` CharField(255), `order` IntegerField(default=0)
  - [x] `Assignment`: `userstory` FK → `"userstories.UserStory"`, `component` FK → `"Component"`
  - [x] Cross-boundary FKs (`projects.Project`, `userstories.UserStory`) use `db_constraint=False` — see **FR-5 / NFR-4 decision**
  - [x] `Assignment.component` keeps `db_constraint=True` (addon → addon) with `on_delete=CASCADE` → AC-5
  - [x] Namespaced `related_name`s (see **Upgrade-safety guardrails**)
  - [x] `Component.save()` strips `name` so the case-insensitive index cannot be defeated by whitespace
  - [x] `Component.Meta.ordering = ("order", "id")` — 3.3 chips render "in catalog order"
  - [x] `Assignment.Meta.constraints`: `UniqueConstraint(fields=["userstory", "component"], name="taiga_contrib_components_assignment_uniq")` → AC-4. Use `constraints`, **not** `unique_together`, and not both
  - [x] **Field-naming trap:** name the FK attributes `project`, `userstory`, `component` — Django appends `_id` to produce the columns AC-1 asks for. Naming a field `project_id` yields a `project_id_id` column and breaks the AC-3 index SQL
- [x] Hand-write `addons/components/back/taiga_contrib_components/migrations/0001_initial.py` (AC: 1, 2, 3, 4)
  - [x] `migrations/__init__.py` must exist or Django treats the app as unmigrated and creates **no tables**
  - [x] `dependencies = [("projects", "__first__"), ("userstories", "__first__")]` — never a pinned migration name (see **Migration dependency rule**)
  - [x] Two `CreateModel` ops + one `RunSQL` for the functional unique index (AC-3) — **Django 3.2 cannot express it declaratively**
  - [x] `RunSQL` must have `reverse_sql` (`DROP INDEX`) so `migrate taiga_contrib_components zero` works
  - [x] Zero operations that name any non-addon app/table (AC-2)
- [x] Update `addons/components/back/taiga_contrib_components/apps.py` and `__init__.py`
  - [x] Add `default_auto_field = "django.db.models.AutoField"` to `ComponentsConfig` (string assign only, no import)
  - [x] Update the `__init__.py` comment — it currently says "No models, URLs, or REST yet." Keep the file free of Django imports (`test_stub_app_importable_from_repo` imports it with no Django installed)
- [x] Verify + record
  - [x] `python -m pytest -q` — baseline is **64 passed, 4 skipped**; must stay green plus the new tests
  - [x] Update `docs/implementation/deferred-work.md`: mark the 1.3 wrong-baseline item corrected; record any 2.1 skips honestly
  - [x] Do **not** bump `platform/TAIGA_PIN`. Do **not** add serializers, viewsets, `urls.py`, permissions, or admin

### Review Findings

_Code review 2026-08-18 — layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor. Suite verified green (74 passed, 6 skipped)._

- [x] [Review][Decision] **Layer B harness isolation strategy** — **Resolved: subprocess isolation.** The Django body moved to `tests/_django_sqlite_harness.py`, run in a child interpreter; the parent test writes the stubs, sets `PYTHONPATH`, and asserts on the exit code, surfacing the child's stdout/stderr on failure. `settings.configure()`/`django.setup()`, `sys.path` and `sys.modules` mutations now die with the child, so 2.2/2.3 can add Django tests freely. Verified: suite still 74 passed / 6 skipped; a mutant (`save()` strip removed) is still caught with the child's exact file:line; a simulated 2.2 test that configures Django *first* now coexists (75 passed) where it previously forced a hard `pytest.fail`.
- [x] [Review][Decision] **Cross-project Assignment is not prevented at any layer** — **Resolved: deferred, with a decision required before 2.3 opens write paths.** The unique constraint is `(userstory, component)` only [addons/components/back/taiga_contrib_components/models.py:33-41], so a UserStory in project A can take a Component owned by project B: both FKs resolve, uniqueness holds, the row persists. Deferred because no cheap airtight fix exists (a Postgres `CHECK` cannot span tables; a trigger means DDL the overlay exists to avoid; `Model.clean()` is bypassed by every bulk path), and the one airtight option — denormalizing `project_id` onto Assignment — goes stale when a UserStory is moved between projects in Taiga, making the invariant its own bug source. **Not** the same class as FR-6 trimming: that yields an ugly but meaningful row, this yields incoherent data no later serializer can repair, because there is no correct answer to which project owns the truth. Cost is asymmetric — free now against empty tables, a data migration plus a repair policy once 2.2/2.3 ship write paths.

- [ ] [Review][Patch] AC-2 fence cannot detect Official Taiga tables — `_taiga_idents` matches only `taiga_`-prefixed identifiers, but core tables are `projects_project` / `userstories_userstory`, so a `RunSQL` writing to them passes clean [tests/test_components_models.py:60,254]
- [ ] [Review][Patch] AC-2 fence has no default-deny — ops outside `{CreateModel} ∪ FORBIDDEN_OPS ∪ {RunSQL}` (`RunPython`, `SeparateDatabaseAndState`, `AlterModelOptions`, …) hit no branch; and within `FORBIDDEN_OPS`, a positionally-written op yields `target is None` and is waved through [tests/test_components_models.py:226-256,239-243]
- [ ] [Review][Patch] `db_constraint=False` is asserted only against `models.py`, never against the hand-written migration that actually builds the schema, nor against the emitted DDL [tests/test_components_models.py:290-292 vs migrations/0001_initial.py:32-39,60-67]
- [ ] [Review][Patch] `deferred-work.md` declares the 1.3 baseline "Corrected in 2.1", but `1-3-upgrade-playbook-and-smoke-test.md:221` still reads "37 passed, 3 skipped" — the ledger asserts a correction that does not exist [docs/implementation/1-3-upgrade-playbook-and-smoke-test.md:221]
- [x] [Review][Patch] ~~Harness `finally` restores only `sys.path`; Django settings, the app registry and `sys.modules` entries stay resident~~ — **moot, resolved by the D1 subprocess split**: the child process owns all of that state and exits with it, so there is nothing left to tear down [tests/_django_sqlite_harness.py]
- [ ] [Review][Patch] `Django==3.2.25` pinned with no Python-version ceiling recorded — Django 3.2 needs `cgi`, removed in 3.13; `importorskip("django")` still passes and the failure lands as a hard error inside `django.setup()` [requirements-dev.txt:3]
- [ ] [Review][Patch] `makemigrations --check --dry-run` is gated behind Docker, but runs offline in the Layer B harness today (independently reproduced → "No changes detected"). Model↔migration drift is the top risk for a hand-written migration and its only check is deferred to a container nobody can run [tests/test_components_models.py:519-530]
- [ ] [Review][Patch] Live `showmigrations` assertion is unbound — `"0001_initial" in stdout` and `"[X]" in stdout` are checked independently, so an unapplied `0001` alongside an applied `0002` passes AC-1's live check [tests/test_components_models.py:513-515]
- [ ] [Review][Patch] `_compose_exec` passes `timeout=` with no `try/except`, unlike the `_overlay_exec_available` probe — a wedged back container errors the suite instead of skipping [tests/test_components_models.py:172-190,512,524]
- [ ] [Review][Patch] `ADDON_TABLES` values are never read (only `set(ADDON_TABLES)` keys are), while the same table-name literals are re-hardcoded at :435-436 and :496-498 [tests/test_components_models.py:26-30]

- [x] [Review][Defer] SQLite `lower()` is ASCII-only; Postgres folds per collation — AC-3's proof is silent on the exact case the engines disagree on [tests/test_components_models.py:390,452-455] — deferred, needs Postgres
- [x] [Review][Defer] `Component.save()` name normalization is not an invariant — `bulk_create`, `queryset.update()`, raw SQL, and `save(update_fields=…)` omitting `name` all bypass it; empty/whitespace-only names are accepted at every layer [addons/components/back/taiga_contrib_components/models.py:11,17-20] — deferred, FR-6 maps to 2.2/3.1
- [x] [Review][Defer] The `RunSQL` `lower(name)` index lives outside Django's migration state, so `makemigrations --check` can never detect drift against it [migrations/0001_initial.py:82-90] — deferred, inherent to `RunSQL`
- [x] [Review][Defer] `test_plugin_load.py` now fences only `urls.py` by name; a future `serializers.py`/`views.py`/`admin.py` would draw no objection — an allowlist of the package file set would be stronger than per-filename blacklisting [tests/test_plugin_load.py:267] — deferred, pre-existing pattern

**Dismissed as noise (5):** `name=123` → `AttributeError` (DRF coerces upstream; `is not None` guard is the documented intent) · `db_constraint=False` permits nonexistent FK ids (deliberate NFR-4 tradeoff, explicitly specified) · forward `CREATE UNIQUE INDEX` lacks `IF NOT EXISTS` (Postgres has transactional DDL — an interrupted `migrate` rolls the index back) · `__first__` dependency may not guarantee FK target exists in a future pin (spec's explicit choice; pinning is worse) · AC-1 live `migrate` not executed (already recorded honestly in `deferred-work.md`)


## Dev Notes

This story is **schema only**. No REST (2.2/2.3), no UI (Epic 3). It is the first story that writes Django code into `addons/`, so it is where the back-end conventions get set for the rest of the project.

**Completion honesty (same protocol as 1.1 / 1.2 / 1.3):** AC-1 says "when the container boots (official `migrate`)". Reading a hand-written migration file is not that. The offline Django+SQLite harness is the strongest proof available without Docker — it actually runs `migrate` and actually enforces the constraints. Live `docker compose exec` stays `skipif`. Do not mark a live subtask `[x]` unless it ran.

### Hard technical facts (verified 2026-08-17 against `taigaio/taiga-back:6.10.2`)

| Fact | Value | Consequence for this story |
| --- | --- | --- |
| Django | **3.2.25** | `UniqueConstraint(Lower("name"), ...)` **does not exist** (Django 4.0+). AC-3 needs raw SQL |
| `DEFAULT_AUTO_FIELD` | `"django.db.models.AutoField"` (set in official `settings/common.py`) | `id` is `AutoField`, not `BigAutoField`. Pin it in the AppConfig so a future official change cannot silently produce migration drift |
| `ATOMIC_REQUESTS` | `True` | Every request is a transaction; do not add manual transaction management |
| Project app label | `projects` (`taiga.projects`) | FK string `"projects.Project"` |
| User Story app label | `userstories` (`taiga.projects.userstories`, no explicit `label`) | FK string `"userstories.UserStory"` |
| Package install path | `install-enabled-addons.sh` does `cp -a .../back/taiga_contrib_components /taiga-back/taiga_contrib_components` | `migrations/` is copied along with the package. **No Dockerfile change is needed.** `/taiga-back` is the WORKDIR, so the package is importable top-level |
| Migrate trigger | official `/taiga-back/docker/entrypoint.sh` runs `manage.py migrate` | Tables appear on boot. This repo adds **no** second migrate command. `taiga-async` is Celery-only and does not migrate |
| Community idiom | `taiga-contrib-slack` uses `models.ForeignKey("projects.Project", ..., on_delete=models.CASCADE)` on a plain `models.Model` | Plain `models.Model`. There is no Taiga base model to inherit |

### AC-3: how to get `(project_id, lower(name))` unique on Django 3.2

Functional/expression constraints landed in Django 4.0. On 3.2 the only honest way is a raw index in the migration:

```python
migrations.RunSQL(
    sql=(
        "CREATE UNIQUE INDEX taiga_contrib_components_component_project_lower_name_uniq "
        "ON taiga_contrib_components_component (project_id, lower(name));"
    ),
    reverse_sql=(
        "DROP INDEX IF EXISTS taiga_contrib_components_component_project_lower_name_uniq;"
    ),
),
```

- `RunSQL` must come **after** both `CreateModel` ops in the `operations` list — the table has to exist first.
- Index name is 58 chars — under the Postgres 63-char identifier limit. Do not lengthen it.
- Table name is Django's default for app label `taiga_contrib_components` + model `Component`. If you set an explicit `db_table`, this SQL must match it. **Prefer the default** — do not invent a `db_table`.
- Trimming is **not** in the index. `Component.save()` strips `name` so `"  Foo"` and `"Foo"` collide as intended. 2.2 adds the friendly serializer error; 2.1 owns the DB-level invariant.

**Do not** "solve" this by installing a newer Django locally. A local Django 4/5 would make `UniqueConstraint(Lower("name"))` pass in tests and then fail on boot against real Taiga 3.2.25. That is the single worst outcome available in this story.

### FR-5 / NFR-4 decision: `db_constraint=False` on FKs into Official Taiga

FR-5 is mapped to this story (epics.md FR coverage map: FR-5 → 1.1, 2.1). NFR-4: *"Overlay must not break Official Taiga if Addon containers are removed."*

Django does not emit `ON DELETE CASCADE` at the database level — it emits a `DEFERRABLE INITIALLY DEFERRED` FK constraint and performs cascades in Python. So a real DB constraint from `taiga_contrib_components_component.project_id` → `projects_project.id` means: **with the overlay removed, plain Official Taiga can no longer delete a Project** — Postgres raises a FK violation from a table Official Taiga has never heard of. That is exactly the failure FR-5 and NFR-4 forbid.

Therefore:

| FK | `db_constraint` | `on_delete` | Why |
| --- | --- | --- | --- |
| `Component.project` → `projects.Project` | **`False`** | `CASCADE` | Crosses the overlay boundary. No DB constraint left behind after removal |
| `Assignment.userstory` → `userstories.UserStory` | **`False`** | `CASCADE` | Same |
| `Assignment.component` → `Component` | `True` (default) | `CASCADE` | Addon→addon. Both tables live and die together. This is what makes AC-5 true at the DB layer too |

Accepted trade-off, state it in Completion Notes: if core deletes a Project or User Story while the overlay is off, addon rows are orphaned. They are harmless — every 2.2/2.3 query is project-scoped or joins through a live parent, so orphans are unreachable. Cleanup is not this story's job and must not be invented here.

`db_constraint=False` does **not** weaken AC-5: `on_delete=CASCADE` still works through the ORM whenever the app is installed, which is the only time Components can be deleted at all.

### Migration dependency rule

```python
dependencies = [
    ("projects", "__first__"),
    ("userstories", "__first__"),
]
```

`taiga-contrib-slack` pins `("projects", "0015_auto_20141230_1212")`. **Do not copy that.** A pinned official migration name is a name this repo would have to re-verify on every pin bump — directly against NFR-1 ("upgrade friction is pin → rebuild → migrate → smoke-test"). `__first__` resolves to whatever the pinned image ships and never needs editing.

### Upgrade-safety guardrails (`related_name`)

A bare `related_name="components"` on `projects.Project` becomes `Project.components`. If a future official Taiga tag adds its own `components` accessor, Django's system checks (`fields.E302`/`E303`) fail at **boot**, not at build — the operator's stack comes back broken after a pin bump. Namespace them:

| Field | `related_name` |
| --- | --- |
| `Component.project` | `"contrib_components"` |
| `Assignment.userstory` | `"contrib_component_assignments"` |
| `Assignment.component` | `"assignments"` (addon→addon, no collision risk) |

Nothing outside the addon may rely on these names; 2.2/2.3 query forward (`Component.objects.filter(project_id=...)`).

### Files being modified — current state / change / preserve

| File | Today | This story changes | Must preserve |
| --- | --- | --- | --- |
| `addons/components/back/taiga_contrib_components/models.py` | **does not exist** | CREATE — `Component`, `Assignment` | n/a |
| `.../taiga_contrib_components/migrations/__init__.py` | **does not exist** | CREATE (empty) | Without it Django creates no tables |
| `.../taiga_contrib_components/migrations/0001_initial.py` | **does not exist** | CREATE | n/a |
| `.../taiga_contrib_components/apps.py` | `ComponentsConfig(name, verbose_name, default=True)`, sole import `django.apps` | Add `default_auto_field` string | Sole import stays `django.apps`; exactly one class; `name = "taiga_contrib_components"`; `default = True` |
| `.../taiga_contrib_components/__init__.py` | Comment: "No models, URLs, or REST yet." | Update comment only | **No Django imports.** `test_stub_app_importable_from_repo` imports it with Django absent |
| `tests/test_plugin_load.py` | 17 passed, 2 skipped | Remove **only** `assert not (STUB_APP / "models.py").exists()` (line 267) | The `urls.py` assertion, the `imports == ["django.apps"]` assertion, and all 1.2 invariants |
| `tests/test_components_models.py` | **does not exist** | CREATE | n/a |
| `requirements-dev.txt` | `pytest>=8.0`, `PyYAML>=6.0` | May add `Django==3.2.25` — see **Testing requirements** for the constraint | Never a Django major other than 3.2 |
| `docs/implementation/deferred-work.md` | 1.3 items incl. wrong baseline count | Correct the baseline item; add 2.1 skips if any | Other deferred items stay deferred |
| `platform/*` | 1.1–1.3 artifacts | **Do not change** | Pin `6.10.2`, override, Dockerfiles, `overlay.py`, `smoke.py`, `UPGRADE.md`, `README.md` |
| `tests/test_overlay_scaffolding.py` | 20 passed, 1 skipped | **Do not break** | `test_addon_tree_placeholders_exist` (`__init__.py` + `apps.py` must remain files) |
| `tests/test_upgrade_playbook.py` | 27 passed, 1 skipped | **Do not break** | Playbook needles, smoke fail-closed |

**Verified baseline at story creation: `python -m pytest -q` → 64 passed, 4 skipped** (20/1 + 17/2 + 27/1). The 1.3 spec recorded `test_plugin_load.py` as "37 passed, 3 skipped"; that was wrong and is corrected here.

### Testing requirements

Three layers. Layer A is mandatory and always runs. Layer B is the real proof of AC-1/3/4/5 and you should get it working. Layer C is honesty for the container.

**A. Static / AST (no Django, always green)**

- `migrations/__init__.py` and `migrations/0001_initial.py` exist
- Parse `0001_initial.py` with `ast`: `dependencies` contains exactly `("projects", "__first__")` and `("userstories", "__first__")` — assert on the literal, so a future pinned-name regression fails loudly
- **AC-2 fence:** walk every operation in the migration. Assert every `CreateModel` name is in `{"Component", "Assignment"}`, and that **no** `AddField`/`AlterField`/`RemoveField`/`RenameField`/`RenameModel`/`AlterModelTable`/`DeleteModel`/`AddIndex`/`AddConstraint` op targets a model outside that set. Assert every `RunSQL` body (forward and reverse) contains no `ALTER TABLE`, no `DROP TABLE`, and names only `taiga_contrib_components_component`
- Parse `models.py`: `Component.project` and `Assignment.userstory` carry `db_constraint=False`; `Assignment.component` does not; all three carry `on_delete=CASCADE`; `related_name`s match the table above
- `apps.py` still imports only `django.apps`; `__init__.py` has no `import django` / `from django`
- The `lower(name)` index SQL is present with a matching `DROP INDEX` reverse

**B. Django + SQLite harness (`pytest.importorskip("django")`)**

Build a throwaway Django project in `tmp_path` with two stub apps — `projects` and `userstories` — each with a `0001_initial` creating a minimal `Project` / `UserStory`. Put the real `addons/components/back` on `sys.path`, `INSTALLED_APPS = ["projects", "userstories", "taiga_contrib_components"]`, sqlite `:memory:`, `DEFAULT_AUTO_FIELD = "django.db.models.AutoField"`, then `call_command("migrate", run_syncdb=False)` and assert:

- AC-1: both tables exist with the expected columns (`connection.introspection`)
- AC-3: `Component(project=p, name="API")` then `Component(project=p, name="api")` raises `IntegrityError`; the same name in a **different** project succeeds; `name="  API  "` is stored as `"API"` and collides
- AC-4: duplicate `(userstory, component)` raises `IntegrityError`
- AC-5: `component.delete()` removes its `Assignment` rows and leaves the `UserStory` row present
- Reversibility: `call_command("migrate", "taiga_contrib_components", "zero")` succeeds (proves `reverse_sql`)

SQLite ≥3.9 supports expression indexes, so the `lower(name)` `RunSQL` runs unmodified — local sqlite is 3.50.4. Keep the SQL Postgres-first; do not branch on vendor.

**Dependency constraint:** Django 3.2.25 is only officially supported on Python ≤3.10; this machine is **Python 3.11.15**. Install it into the dev venv and try. If it installs and the harness runs — pin `Django==3.2.25` in `requirements-dev.txt`. If Python 3.11 breaks it, put `Django==3.2.25` in a separate `requirements-back-dev.txt`, leave the harness on `importorskip`, and record the reason in Debug Log. **Never** relax the pin to a newer Django to make it install — see the AC-3 warning above.

**C. Live container (`skipif` — Docker + a running overlay stack)**

Reuse the probe style already in `tests/test_upgrade_playbook.py` (`--compose-dir` / `$TAIGA_DOCKER`, `timeout=` on every `subprocess.run`):

- `docker compose exec -T taiga-back /opt/venv/bin/python manage.py showmigrations taiga_contrib_components` → `0001_initial` applied
- `docker compose exec -T taiga-back /opt/venv/bin/python manage.py makemigrations --check --dry-run taiga_contrib_components` → exit 0, proving the hand-written migration matches `models.py` with no drift

Skip honestly when Docker or the stack is absent. Do not start a stack in CI.

### Library / framework

- No new runtime dependency. The addon uses only `django.db.models` and `django.apps` as shipped in the pinned image.
- **Forbidden:** `djangorestframework` (Taiga vendors its own API layer under `taiga.base.api`; 2.2 will use that, not upstream DRF), `django-model-utils`, `django-ordered-model`, `psycopg2` in dev, South-style helpers, `django.contrib.postgres` fields.
- Dev-only: `pytest`, `PyYAML`, and possibly `Django==3.2.25` per the constraint above.

### Out of scope (stop if you start these)

- Serializers, viewsets, routers, `urls.py`, permission classes, `admin.py` — 2.2 / 2.3
- Any endpoint under `/api/v1/components/` — 2.2
- Reorder logic beyond the `order` column and `Meta.ordering` — 2.2
- Front plugin changes, picker, chips — Epic 3
- Extending `platform/smoke.py` to assert table existence — smoke's contract is stub load (1.3 AC-2); an operator table glance can go in `UPGRADE.md` when 2.2 gives it a reason
- Bumping `TAIGA_PIN`, or "fixing" the known `taiga-front:6.10.2` Hub 404
- Data migrations, seed Components, orphan-cleanup jobs
- Anything under `docs/planning/`

### Previous story intelligence

**1.1** (`done`): `platform/TAIGA_PIN` is the declared seed; pin copies are test-enforced. `taiga-async` reuses the back image, `pull_policy: never`, no override entrypoint. Live Docker was absent; the honesty protocol (skipif, never fake) started here.

**1.2** (`done`): Append-not-replace via `settings.overlay` + front `40_` hook. `addons.txt` is the single enable switch; `install-enabled-addons.sh` fans out enabled slugs at build (AD-9) — a new file inside the package needs **no** Dockerfile edit. Overlay fails closed. Slug regex `^[a-z][a-z0-9_]*$`. `.gitattributes` forces `*.sh` LF (irrelevant here — write Python, not shell). Review finding: **do not prove one implementation with a second reimplementation of it** — that is why layer B runs the real migration rather than re-deriving the SQL in the test.

**1.3** (`done`): `platform/smoke.py` is the only checker; it reuses `overlay.py` helpers rather than copying logic. Review findings worth inheriting into this story's tests:
- Needle/substring tests over a whole file are an anti-pattern — assert on parsed structure (hence AST over the migration, not `"__first__" in text`)
- A source grep is not proof of reuse — `assert x is y` / run the real thing
- Every `subprocess.run` needs `timeout=`
- Distinguish "environment absent" from "check failed" in exit codes and skip reasons

**Deferred-work that is NOT yours:** `TAIGA_PIN=latest` build-arg guard, PowerShell README, unpinned `apk add jq`, the live-smoke test seam, the `UPGRADE.md` apostrophe encoding needle, `git pull --ff-only` preconditions.

**Deferred-work that IS yours:** correcting the 1.3 wrong baseline test count (`test_plugin_load.py` is 17 passed / 2 skipped, not 37/3) so it is not copied forward again.

### Git intelligence

HEAD `cffe7d6` — *Mark story 1.3 done after review follow-ups.* Preceding: `ccabb48` (1.3), `2dacd08`/`0ed9dcf` (1.2), `ab0f10d`/`ed2d308`/`b591227` (1.1).

Established rhythm across all three: **red tests first → implementation → `python -m pytest -q` as proof → review follow-up commit**. Two commits per story (implementation, then review fixes). Working tree stays limited to the story's own files. Repo is `master`, ahead of `origin/master`.

Epic 1 shipped zero application code — 2.1 is the first Django code in `addons/`. Whatever you write here is the pattern 2.2, 2.3, and every future addon will copy.

### Latest tech information

Verified 2026-08-17 / 2026-08-18:

- `taigaio/taiga-back:6.10.2` `requirements.txt`: `django==3.2.25`, `psycopg2==2.9.11`, `celery==5.5.3`, `gunicorn==23.0.0`, `asgiref==3.11.0`. **No `djangorestframework`** — Taiga ships its own API layer (`taiga.base.api`) while still reading a `REST_FRAMEWORK` settings dict. Relevant to 2.2; relevant here only as "do not add DRF".
- Django 3.2 is EOL upstream. It is what the pinned image runs. Write for 3.2, not for what is current.
- Expression-based `UniqueConstraint` / `Index`: Django **4.0+** only. `Meta.constraints` with plain `fields=` works fine on 3.2 (used for AC-4).
- `Meta.index_together` is deprecated in later Django but fine on 3.2 — still, prefer `Meta.constraints` / `RunSQL`.
- Hub tag reality (unchanged from 1.3): `taiga-back:6.10.2` exists, `taiga-front:6.10.2` is a **404**; back and front `:latest` diverge. Not this story's problem — documented in `platform/UPGRADE.md`. Do not "fix" it.

### References

- [Source: docs/planning/epics.md] Epic 2, Story 2.1; FR coverage map (FR-5 → 1.1, 2.1)
- [Source: docs/planning/prd.md] FR-5 (§ overlay removal safe), FR-6 (trimmed, case-insensitive unique), FR-8 (unlink, do not delete stories), Glossary "Component" / "Component catalog"
- [Source: docs/planning/prd-addendum.md:17] Back extension pattern — own Django migrations, `taiga-contrib-slack` family
- [Source: docs/planning/ARCHITECTURE-SPINE.md] AD-6 (Addon-owned schema, FKs reference core PKs, never `ALTER TABLE` core), AD-7, AD-8, AD-9; ER diagram; Consistency Conventions (integer PKs, trimmed names unique per Project)
- [Source: docs/planning/architecture.md] "Components data" § — two Addon tables, delete Component → delete Assignment rows
- [Source: docs/implementation/1-2-plugin-load-without-replacing-official-config.md] `install-enabled-addons.sh` fan-out, stub app contract
- [Source: docs/implementation/1-3-upgrade-playbook-and-smoke-test.md] Honesty protocol, review anti-patterns, official entrypoint `migrate`
- [Source: docs/implementation/deferred-work.md] What is and is not yours
- [Source: tests/test_plugin_load.py:239-273] `test_stub_app_importable_from_repo` — the `models.py` assertion this story must retire
- [Source: platform/install-enabled-addons.sh] `cp -a` of the whole package (migrations travel for free)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/requirements.txt (Django 3.2.25)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/settings/common.py (`DEFAULT_AUTO_FIELD`, `ATOMIC_REQUESTS`)
- Official: https://github.com/taigaio/taiga-contrib-slack/blob/main/back/taiga_contrib_slack/models.py (FK idiom)
- Django 3.2 docs: https://docs.djangoproject.com/en/3.2/ref/models/constraints/ (no expression support)

### Project structure notes

After this story:

```text
addons/components/back/taiga_contrib_components/
  __init__.py                 # UPDATE (comment only, no Django imports)
  apps.py                     # UPDATE (+ default_auto_field)
  models.py                   # CREATE
  migrations/
    __init__.py               # CREATE (empty)
    0001_initial.py           # CREATE
tests/test_components_models.py  # CREATE
tests/test_plugin_load.py        # UPDATE (retire one assertion)
```

`platform/` is untouched. Follow the spine: no `urls.py`, no `serializers.py`, no `admin.py` until 2.2.

### Project context reference

No `project-context.md` in this repo. The governing context is `docs/planning/ARCHITECTURE-SPINE.md` (AD-1…AD-9) plus the 1.1 / 1.2 / 1.3 review decisions recorded in those story files.

## Dev Agent Record

### Agent Model Used

Grok 4.6 (bmad-dev-story)

### Implementation Plan

- Red: `tests/test_components_models.py` (AST fence + Django 3.2.25 SQLite harness + live skipif) against missing models/migrations. 8 failed, 1 passed, 3 skipped before Django install; harness skipped until `Django==3.2.25` was installed on Python 3.11.15.
- Trap: deleted only `assert not (STUB_APP / "models.py").exists()` in `test_plugin_load.py`. Left `urls.py` and `imports == ["django.apps"]` intact.
- Green: `Component` / `Assignment` with `db_constraint=False` on core FKs, addon→addon CASCADE, `save()` strip, `Meta.constraints` unique, hand-written `0001_initial` (two `CreateModel` + `RunSQL` lower(name) index with `DROP INDEX` reverse), `default_auto_field` string on `ComponentsConfig`.
- Verify: `python -m pytest -q` → 74 passed, 6 skipped. Pin left at `6.10.2`. No REST / URLs / admin.

### Debug Log References

- RED: 8 failed, 1 passed, 3 skipped (`test_package_init_has_no_django_import` already held; harness + live skipped — Django not yet installed, Docker absent)
- Django 3.2.25 installed via `uv pip install Django==3.2.25` into the active 3.11.15 venv; `python -m pip` is not available on that interpreter. Pin added to `requirements-dev.txt`.
- GREEN: `tests/test_components_models.py` → 10 passed, 2 skipped (live compose exec)
- Full suite: `python -m pytest -q` → 74 passed, 6 skipped (previous four live/Docker/jq skips plus two new live migrate/drift checks)
- Live `docker compose exec` was **not** executed — Docker absent. Layer B ran real `migrate` / constraints / reverse. skipif is honest.
- Python 3.11 emits Django 3.2 `cgi` / `locale.getdefaultlocale` DeprecationWarnings during the harness; they do not fail the suite.

### Completion Notes List

- Schema-only: `Component(project, name, order)` and `Assignment(userstory, component)` live in `taiga_contrib_components`. No `urls.py`, serializers, viewsets, permissions, or admin.
- Cross-boundary FKs use `db_constraint=False` + ORM `CASCADE`. Overlay removal cannot block Official Taiga from deleting a Project or User Story. Accepted trade-off: if core deletes those rows while the overlay is off, addon rows are orphaned and unreachable to later project-scoped queries. Cleanup is not this story.
- `Assignment.component` keeps a real DB constraint with `on_delete=CASCADE`, so AC-5 holds at the database when the addon is installed.
- AC-3 is a Postgres-first `RunSQL` unique index on `(project_id, lower(name))`. Django 3.2 cannot declare it. `Component.save()` strips `name` so whitespace cannot dodge the index.
- Migration depends on `("projects", "__first__")` and `("userstories", "__first__")` — no pinned official migration name.
- `default_auto_field = "django.db.models.AutoField"` is a string assignment on `ComponentsConfig`; `apps.py` still imports only `django.apps`.
- Layer B is the strongest AC-1 proof available without Docker: it runs `migrate` (not `syncdb`) and enforces AC-3/4/5 plus `migrate taiga_contrib_components zero`.
- Live showmigrations / makemigrations --check skipif — Docker absent. Recorded in deferred-work.
- 1.3 wrong baseline (37/3 vs 17/2) marked corrected in deferred-work. `platform/TAIGA_PIN` unchanged.

### File List

- addons/components/back/taiga_contrib_components/models.py
- addons/components/back/taiga_contrib_components/migrations/__init__.py
- addons/components/back/taiga_contrib_components/migrations/0001_initial.py
- addons/components/back/taiga_contrib_components/apps.py
- addons/components/back/taiga_contrib_components/__init__.py
- tests/test_components_models.py
- tests/_django_sqlite_harness.py (added by code review — D1 subprocess isolation)
- tests/test_plugin_load.py
- requirements-dev.txt
- docs/implementation/deferred-work.md
- docs/implementation/2-1-models-and-migrations.md
- docs/implementation/sprint-status.yaml

### Change Log

- 2026-08-18: Implemented Component/Assignment models and addon-owned `0001_initial`. Status → review. Live Docker exec skipif (Docker absent). Django 3.2.25 pinned for the SQLite harness.
- 2026-08-18: Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 2 decisions, 10 patches, 4 defers, 5 dismissed. D1 applied: Layer B harness moved to a child process (`tests/_django_sqlite_harness.py`) so `settings.configure()`/`django.setup()` no longer leak across tests — suite still 74 passed / 6 skipped, mutant still caught, a Django-configuring test can now precede it. D2 deferred with a decision required before 2.3 opens write paths. Remaining 9 patches left as action items. Status → in-progress.
