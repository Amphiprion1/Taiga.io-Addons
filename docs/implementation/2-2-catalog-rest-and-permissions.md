---
baseline_commit: 38d7f92
---

# Story 2.2: Catalog REST and permissions

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a project admin,
I want to create, list, reorder, rename, and delete Components via API,
so that the catalog is the only source of names for that Project.

## Acceptance Criteria

1. **Given** I am a project admin **When** I POST/PATCH/DELETE/reorder on `/api/v1/components` for my Project **Then** the catalog updates and uniqueness (trimmed, case-insensitive) is enforced
2. **And** another Project never sees these Components
3. **Given** I am a project member but not admin **When** I GET the catalog **Then** I receive the list
4. **And** write operations return 403
5. **Given** I am unauthenticated **When** I call catalog endpoints **Then** I receive 401
6. **Given** a Component with Assignments **When** an admin deletes it **Then** Assignment rows are removed and User Stories remain

## Tasks / Subtasks

- [x] **Red first** — write the tests before the implementation (repo pattern from 1.1–2.1)
  - [x] `tests/test_components_api.py` — Layer A (AST/static, always runs) per **Testing requirements**
  - [x] Extend the Layer B harness (`tests/_django_sqlite_harness.py` + `tests/_taiga_stub/`) — real `services.py` execution + real `apps.ready()` route registration
  - [x] Layer C live `docker compose exec` HTTP checks behind `skipif`
- [x] **Fix the 2.1 regression traps BEFORE writing `apps.py` / `api.py`** (AC: all)
  - [x] `tests/test_plugin_load.py:255` — `assert imports == ["django.apps"]` uses `ast.walk`, so it sees imports **nested inside `ready()`** too. 2.2 legitimately invalidates it. Replace with: module-**top-level** imports (`tree.body` only) are exactly `["django.apps"]`, **and** the `ready()` body imports exactly the expected `taiga.*` / relative modules. Do not simply delete the assertion — the intent (no Django/Taiga import at package-import time) is still load-bearing
  - [x] `tests/test_plugin_load.py:267` — `assert not (STUB_APP / "urls.py").exists()` is a per-filename blacklist flagged in `deferred-work.md`. Replace it with an **allowlist** of the package's file set (see **File structure**). This closes that deferred item and is cheaper now than after 2.3
  - [x] Do **not** weaken `test_stub_app_importable_from_repo`'s core contract: `taiga_contrib_components/__init__.py` must still import with **no Django and no Taiga installed**, and `apps.py` must still contain exactly one class named `ComponentsConfig` with `name = "taiga_contrib_components"`
- [x] **`services.py` — pure, offline-provable domain logic** (AC: 1, 2, 6)
  - [x] `normalize_name(name)` — trim; the single definition of "trimmed"
  - [x] `name_conflicts(project_id, name, exclude_pk=None) -> bool` — case-insensitive (`__iexact`) match on the normalized name within `project_id`, excluding `exclude_pk` on rename
  - [x] `bulk_update_component_order(project, user, data)` — ORM, **not** raw Postgres SQL (see **Reorder**)
  - [x] Imports **only** `django.db` + `.models`. No `taiga.*` import in this file — that is what makes it real-testable in Layer B
- [x] **`validators.py`** (AC: 1, 2)
  - [x] `ComponentValidator(validators.ModelValidator)` with `Meta.model = Component`, `Meta.fields = ("id", "project", "name", "order")`
  - [x] `validate_name(self, attrs, source)` — **old DRF-2 signature**, see **Validator idiom**. Normalize, reject empty/whitespace-only, reject `services.name_conflicts(...)` with a 400
  - [x] `validate_project(self, attrs, source)` — reject changing `project` on update (`self.object` exists and `attrs["project"]` differs) → this is what closes the PATCH-to-another-project hole (AC-2)
- [x] **`permissions.py`** (AC: 3, 4, 5)
  - [x] `ComponentPermission(TaigaResourcePermission)` with the exact `*_perms` table in **Permissions**
- [x] **`serializers.py`** (AC: 1, 3)
  - [x] `ComponentSerializer(serializers.LightSerializer)`: `id = Field()`, `name = Field()`, `order = Field()`, `project = Field(attr="project_id")`. **No `I18NField`** — Component names are user data, not translated catalog seeds
- [x] **`api.py`** (AC: 1, 2, 3, 4, 5, 6)
  - [x] `ComponentViewSet(ModelCrudViewSet, BulkUpdateOrderMixin)` with the attribute set in **ViewSet shape**
  - [x] **Override `list()`** — `ListModelMixin.list()` never calls `check_permissions`. Without this override, AC-5 is unreachable for `GET /api/v1/components` (see **The 401 trap**)
- [x] **`apps.py` — register the router in `ready()`** (AC: 1)
  - [x] Follow the `taiga-contrib-slack` idiom verbatim (see **URL registration**). All `taiga.*` and relative imports stay **inside** `ready()`
- [x] **`UPGRADE.md`** — add the catalog endpoint to the operator smoke glance (AC: 1)
  - [x] Story 2.1 explicitly deferred this "until 2.2 gives it a reason". One authenticated `curl` line for `GET /api/v1/components?project=<id>`. **Do not** touch `platform/smoke.py` — its contract is stub load (1.3 AC-2)
- [x] **Verify + record**
  - [x] `python -m pytest -q` — baseline is **80 passed, 6 skipped**; must stay green plus the new tests
  - [x] Update `docs/implementation/deferred-work.md`: record 2.2 live skips honestly, record the anonymous-public-project consequence (see **Flagged consequence**), mark the file-allowlist deferred item resolved

- [x] **Review Follow-ups (AI)**
  - [x] [AI-Review] Malformed `bulk_components` payload 400s via `api.py` wrapper
  - [x] [AI-Review] Anti-drift guard symbol-checks name-reached stub modules
  - [x] [AI-Review] Layer C skips only on pre-flight; in-stack exceptions fail
  - [x] [AI-Review] Live test uses a per-run random password
  - [x] [AI-Review] Cross-project POST 201 is tracked for cleanup
  - [x] [AI-Review] `UPGRADE.md` catalog glance defines `TAIGA_URL` and fails closed
  - [x] [AI-Review] ViewSet shape test is default-deny; `list` returns `super().list`; `Field` is exact
  - [x] [AI-Review] Harness asserts `urlpatterns` grew by one
  - [x] [AI-Review] Package allowlist has one source (`tests/_addon_package.py`)
  - [x] [AI-Review] Deferred-work records AC-1/AC-2 live gap and the 401/membership narrowings
  - [x] [AI-Review] Completion Notes record the `UPGRADE.md` "do not curl yet" deletion

## Dev Notes

This story is **back-end REST only**. No UI (Epic 3), no Assignment endpoints (2.3). It is the first story that touches Taiga's own API layer, so the idioms chosen here are the ones 2.3 and every future addon will copy.

**Completion honesty (same protocol as 1.1–2.1):** ACs 3/4/5 are HTTP status assertions against a real Taiga stack. Layer B cannot produce them — see **What Layer B can and cannot prove**. Do not mark a live subtask `[x]` unless it ran. Record the gap in `deferred-work.md`.

### Hard technical facts (verified 2026-08-18 against `taigaio/taiga-back:6.10.2` source)

| Fact | Value | Consequence |
| --- | --- | --- |
| API layer | `taiga.base.api` — a **vendored DRF-2 fork**, not upstream DRF | No `djangorestframework` dependency. Validators use the old `validate_<field>(self, attrs, source)` signature and a `.object` attribute |
| `ModelCrudViewSet` | `taiga.base.api.viewsets` — Create + Retrieve + Update + Destroy + List mixins | Gives all of AC-1's verbs |
| Router | `taiga.base.routers.DefaultRouter(trailing_slash=False)` | Routes are **slashless**: `/api/v1/components`, `/api/v1/components/<pk>`. `/api/v1/components/` (with slash) **404s**. The epic's `/api/v1/components/` means the collection, not a literal trailing slash |
| Router register kwarg | `base_name=`, not `basename=` | Old-DRF signature |
| `get_queryset()` | falls back to `self.model._default_manager.all()` | Set `model = Component`; do not hand-roll a queryset |
| `ListModelMixin.list()` | **does not call `check_permissions` at all** | See **The 401 trap** |
| `RetrieveModelMixin.retrieve()` | `get_object_or_404(self.get_queryset(), **kwargs)` — the **unfiltered** queryset — then `check_permissions(request, "retrieve", obj)` | Cross-project retrieve is stopped by `retrieve_perms`, **not** by the filter backend |
| `update` / `destroy` | `get_object_or_none()` → `get_object()` → `filter_queryset(get_queryset())` | Foreign-project pk yields 404 before permissions |
| `permission_denied()` | `raise NotAuthenticated()` if `not request.successful_authenticator`, else `PermissionDenied()` | 401 vs 403 is automatic — **if** a permission check actually runs |
| 401 requires a `WWW-Authenticate` header | `handle_exception` downgrades `NotAuthenticated` → **403** when `get_authenticate_header()` is falsy | `DEFAULT_AUTHENTICATION_CLASSES[0]` is `taiga.auth.authentication.JWTAuthentication`, which **does** define `authenticate_header()` (`Bearer realm="api"`). So anonymous → genuine **401**. AC-5 is reachable |
| `_get_object_project(obj)` | Project → itself; else `obj.project` if present; else `None` → permission `False` | `IsProjectAdmin()` on `create` resolves the project from the **posted** `project` field via `validator.object.project` |
| `create` permission timing | `CreateModelMixin.create()` validates **first**, then `check_permissions(request, "create", validator.object)` | A create with a bad name returns **400 before 403**. Do not write a test that asserts 403 for a non-admin posting an invalid payload |
| `ATOMIC_REQUESTS` | `True` | No manual transaction management |
| Pagination | `PAGINATE_BY: 30`, `PAGINATE_BY_PARAM: "page_size"` | A >30-component catalog paginates. Leave the default; 3.1 owns the UI consequence |

### The 401 trap (AC-5) — read this twice

Official Taiga catalogs (`SeverityViewSet`, `UserStoryStatusViewSet`) declare `list_perms = AllowAny()`. That is **not** a policy choice — `ListModelMixin.list()` never calls `check_permissions`, so `list_perms` is decorative. All list scoping is done by `CanViewProjectFilterBackend`, which for an anonymous user returns `qs.filter(project__anon_permissions__contains=["view_project"])` — i.e. **HTTP 200 with a filtered list**, never 401.

AC-5 requires 401 on *catalog endpoints*, list included. So `ComponentViewSet` must override:

```python
def list(self, request, *args, **kwargs):
    self.check_permissions(request, "list", None)
    return super().list(request, *args, **kwargs)
```

with `list_perms = IsAuthenticated()`. Anonymous → `NotAuthenticated` → 401. Authenticated non-member → 200 with an empty list (the filter backend removes rows they cannot see) — that satisfies AC-2 and does not contradict AC-3.

Do **not** try to solve this with `global_perms`; `global_perms` is ANDed inside `ResourcePermission.check_permissions`, which `list()` never calls.

### Flagged consequence of AC-5 (state it, then implement AC-5 as written)

Closing anonymous list/retrieve means a **public** Taiga project viewed by a logged-out visitor gets 401 from the catalog, where official Taiga catalogs return 200. That is what AC-5 and PRD FR-10 ("Unauthenticated requests are rejected") ask for, so implement it. But it will resurface in **3.3 chips** if chips must render for anonymous visitors on a public project. Record it in `deferred-work.md` as a known v1 narrowing with 3.3 as the story that must revisit it. Do not pre-solve it here.

### Permissions (AD-7 → exact code)

```python
from taiga.base.api.permissions import TaigaResourcePermission
from taiga.base.api.permissions import IsAuthenticated
from taiga.permissions.permissions import HasProjectPerm
from taiga.permissions.permissions import IsProjectAdmin


class ComponentPermission(TaigaResourcePermission):
    list_perms = IsAuthenticated()
    retrieve_perms = IsAuthenticated() & HasProjectPerm("view_project")
    create_perms = IsProjectAdmin()
    update_perms = IsProjectAdmin()
    partial_update_perms = IsProjectAdmin()
    destroy_perms = IsProjectAdmin()
    bulk_update_order_perms = IsProjectAdmin()
```

- `IsProjectAdmin` and `HasProjectPerm` live in **`taiga.permissions.permissions`**, not `taiga.base.api.permissions`. Getting this wrong is an `ImportError` at container boot, i.e. a broken stack after `up -d`.
- `TaigaResourcePermission` already supplies `enough_perms = IsSuperUser()`. Do not redeclare it.
- `PermissionComponent` overloads `&`, `|`, `~` — `IsAuthenticated() & HasProjectPerm(...)` is the supported idiom.
- `IsAuthenticated()` on `retrieve` is **required**: bare `HasProjectPerm("view_project")` passes for an anonymous user on a public project, which would return 200 and break AC-5.
- Every action you route must have a `*_perms` attribute. A missing one is a silent hole.

### ViewSet shape

```python
class ComponentViewSet(ModelCrudViewSet, BulkUpdateOrderMixin):
    model = models.Component
    serializer_class = serializers.ComponentSerializer
    validator_class = validators.ComponentValidator
    permission_classes = (permissions.ComponentPermission,)
    filter_backends = (filters.CanViewProjectFilterBackend,)
    filter_fields = ("project",)
    bulk_update_param = "bulk_components"
    bulk_update_perm = "change_component"
    bulk_update_order_action = services.bulk_update_component_order
```

Imports: `from taiga.base.api.viewsets import ModelCrudViewSet`, `from taiga.base import filters`, `from taiga.projects.mixins.ordering import BulkUpdateOrderMixin`.

- `filter_fields = ("project",)` is **mandatory**, not cosmetic: `PermissionBasedFilterBackend.filter_queryset` only reads `?project=` when `"project" in view.filter_fields`, and `QueryParamsFilterMixin` needs it to apply the `project=<id>` filter at all.
- MRO order `ModelCrudViewSet, BulkUpdateOrderMixin` mirrors official. Keep it.
- `bulk_update_order_action = services.bulk_update_component_order` is a **plain function assignment**. The mixin calls `self.__class__.bulk_update_order_action(project, user, data)`; class-attribute access on a function does not bind `self`, so a plain `def` with three parameters is correct. Do not wrap it in `staticmethod` "to be safe" and do not give it a `self`.
- `bulk_update_perm` is required by the mixin's docstring but is **never read** in 6.10.2's mixin body; the real gate is `bulk_update_order_perms`. Set both anyway to match official.
- Official catalogs also mix in `MoveOnDestroyMixin`, `ArchivedByProjectMixin`, `BlockedByProjectMixin`. **Out of scope here** — none is required by an AC, and each drags in behaviour (destination-on-delete, archived filtering) that no story has specified. Note the decision in Completion Notes so a reviewer does not read the omission as an oversight.

### Reorder (FR-9, AC-1)

Reuse `BulkUpdateOrderMixin` — do not hand-roll an endpoint. It gives you:

- `POST /api/v1/components/bulk_update_order`
- Body: `{"project": <id>, "bulk_components": [[<component_id>, <order>], ...]}`
- 400 if either key is missing; 404 if the project does not exist; `check_permissions(request, "bulk_update_order", project)`; `exc.Blocked` if `project.blocked_code is not None`; **204 No Content** on success.

Write your own action. Official `bulk_update_*_order` functions use raw Postgres `PREPARE`/`EXECUTE` cursors — copying that would make the logic untestable in Layer B (SQLite) and add a Postgres-dialect dependency the addon does not need:

```python
@transaction.atomic
def bulk_update_component_order(project, user, data):
    for component_id, order in data:
        Component.objects.filter(project_id=project.id, id=component_id).update(order=order)
```

The `project_id=project.id` predicate is the AC-2 guard: an id from another project silently updates zero rows rather than reordering a foreign catalog. Keep it.

`user` is unused — the parameter exists because the mixin passes it positionally. Do not rename or drop it.

### Verb map and the `order` default

| Operation | Request | Notes |
| --- | --- | --- |
| Create (FR-6) | `POST /api/v1/components` `{"project": <id>, "name": "API", "order": <int>}` | 201 |
| List (FR-9) | `GET /api/v1/components?project=<id>` | Ordered by `Meta.ordering = ("order", "id")` from 2.1 |
| Rename (FR-7) | `PATCH /api/v1/components/<pk>` `{"name": "..."}` | Prefer PATCH. **`PUT` runs the same `update()` with `partial=False`**, so a PUT that omits `project` will fail validation — that is correct, not a bug to work around |
| Reorder (FR-9) | `POST /api/v1/components/bulk_update_order` | 204 |
| Delete (FR-8) | `DELETE /api/v1/components/<pk>` | 204, unlinks Assignments (spine: unlink, not 409) |

`Component.order` defaults to `0` (2.1), so components created without an explicit `order` all tie at 0 and fall back to `id` ordering — effectively creation order. That is acceptable for this story: `order` is in the validator's `fields`, so a client may set it, and 3.1 owns "append at end" in the UI. **Do not** add auto-increment-on-create logic here; no AC asks for it and it would need a second write inside `create()`.

### Validator idiom (this is a DRF-2 fork, not modern DRF)

```python
class ComponentValidator(validators.ModelValidator):
    class Meta:
        model = models.Component
        fields = ("id", "project", "name", "order")

    def validate_name(self, attrs, source):
        ...
        return attrs
```

- Signature is `(self, attrs, source)` and it returns **`attrs`**, not the value. Modern DRF's `validate_name(self, value)` will never be called and your uniqueness check will silently not run — a green suite hiding a broken AC-1.
- `self.object` is the existing instance on update, `None` on create. Use it for the `exclude_pk` on rename and for the project-change rejection.
- On create, `attrs.get("project")` is a **Project instance** (already coerced by the model field), so use `attrs["project"].id` / `attrs["project"].pk` when calling `services.name_conflicts`.
- Raise `taiga.base.exceptions.ValidationError(_("..."))` → 400. Compare with `taiga.projects.validators.DuplicatedNameInProjectValidator`, which is exact-match only; ours must be **case-insensitive on the trimmed name** to match the DB index from 2.1.
- Without this validator the 2.1 `(project_id, lower(name))` unique index raises `IntegrityError` → **500**, not 400. That is the failure mode AC-1 is really guarding.

### What 2.1 did and did not leave you (read `deferred-work.md`)

- `Component.save()` strips `name`, but that is a **convention, not an invariant** — `bulk_create`, `QuerySet.update()`, and `save(update_fields=[...])` without `"name"` all bypass it, and empty/whitespace-only names are accepted at every layer. 2.1 explicitly flagged that FR-6 (trimmed, non-empty) is **2.2's job**. Normalize in `services.normalize_name` and enforce non-empty in the validator; do not assume the model did it.
- The `lower(name)` unique index exists and is real. Your validator produces the friendly 400; the index is the backstop.
- `Assignment` CASCADE from `Component` is a **real DB constraint** (`db_constraint` default `True` on that addon→addon FK). AC-6 is therefore already true at the database level — your job is to prove it through the API path, not to re-implement unlinking. Do **not** add manual `Assignment.objects.filter(...).delete()` in `destroy`.
- `Component.project` and `Assignment.userstory` use `db_constraint=False` deliberately (NFR-4). Do not "fix" this.
- **Not yours:** the cross-project Assignment hole (`deferred-work.md`, 2.1 review) — that is 2.3's decision. Do not denormalize `project_id` onto `Assignment` here.

### URL registration (`apps.py`)

Verbatim idiom from `taiga-contrib-slack/back/taiga_contrib_slack/apps.py`:

```python
class ComponentsConfig(AppConfig):
    name = "taiga_contrib_components"
    verbose_name = "Components"
    default = True
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from django.urls import include, path
        from taiga.base import routers
        from taiga.urls import urlpatterns
        from .api import ComponentViewSet

        router = routers.DefaultRouter(trailing_slash=False)
        router.register(r"components", ComponentViewSet, base_name="components")
        urlpatterns.append(path("api/v1/", include(router.urls)))
```

- Every import stays **inside** `ready()`. Module scope keeps only `from django.apps import AppConfig` — importing `taiga.urls` at module level is an app-registry-not-ready crash at boot.
- `ready()` runs on **every** process using this image: `taiga-back` (gunicorn) and `taiga-async` (celery, AD-4). Registration must be idempotent and side-effect-free beyond appending routes. Do not add signals, network calls, or DB queries.
- `default = True` is what makes Django pick this AppConfig from a bare `INSTALLED_APPS` string. Keep it.

### `ready()` breaks the existing Layer B harness — handle it first

`tests/_django_sqlite_harness.py` puts `taiga_contrib_components` in `INSTALLED_APPS`; `django.setup()` calls `ready()`; `ready()` imports `taiga.*`, which is **not installed on the dev machine**. Story 2.1's proof of AC-1/3/4/5 will start failing with `ModuleNotFoundError` the moment you write `ready()`. Fix this before you write `api.py`, or you will be debugging 2.1 while implementing 2.2.

Approach — a **checked-in, minimal import-shim** at `tests/_taiga_stub/taiga/`:

- Provide only the names the addon actually imports: `taiga.base.routers.DefaultRouter` (records `register()` calls), `taiga.urls.urlpatterns` (a list), and no-op stand-ins for the symbols `api.py` / `permissions.py` / `validators.py` / `serializers.py` import.
- Put `tests/_taiga_stub` on the child's `PYTHONPATH` alongside `tmp_path` and `STUB_BACK`.
- **Anti-drift guard (required):** a Layer A test that walks the addon package with `ast`, collects every `taiga.*` module and symbol it imports, and asserts the stub provides exactly that set — no more, no less. This is what keeps the shim from quietly becoming a second implementation of Taiga. The 1.2 review's rule still binds: *do not prove one implementation with a second reimplementation of it*. The shim exists to let imports resolve, **not** to answer questions about behaviour.
- The stub must never be importable from production code paths — it lives under `tests/` and is only added to `sys.path` by the harness child.

Whatever you do, do **not** wrap `ready()`'s body in `try/except ImportError`. That fails open: a real import error in production would silently unregister the whole API and the only symptom would be 404s.

### What Layer B can and cannot prove

| AC | Provable offline? | How |
| --- | --- | --- |
| AC-1 uniqueness (trimmed, case-insensitive) | **Yes** | `services.name_conflicts` + `normalize_name` run for real against SQLite |
| AC-1 reorder | **Yes** | `services.bulk_update_component_order` is pure ORM |
| AC-1 verbs reachable at the right URLs | Partly | Router registration asserted via the shim; real HTTP is Layer C |
| AC-2 project scoping | Partly | `bulk_update_component_order`'s `project_id` predicate and `name_conflicts` scoping run for real; the filter-backend path is Layer C |
| AC-3 / AC-4 / AC-5 (200 / 403 / 401) | **No** | Requires real Taiga permissions + JWT. Layer A asserts the `*_perms` wiring by AST; Layer C asserts the status codes |
| AC-6 | **Yes** | Already proven by 2.1's harness (`component.delete()` removes Assignments, UserStory survives). Add the API-path assertion in Layer C |

Say this plainly in Completion Notes. Claiming AC-3/4/5 without Docker is the one failure this project's review process reliably catches.

### Testing requirements

Three layers, same shape as 2.1.

**A. Static / AST (`tests/test_components_api.py`, always runs)**

- `permissions.py`: parse the class; assert the exact `*_perms` attribute set and each right-hand side — `list_perms` is `IsAuthenticated()`, `retrieve_perms` is `IsAuthenticated() & HasProjectPerm("view_project")`, the four write actions plus `bulk_update_order_perms` are `IsProjectAdmin()`. Assert `IsProjectAdmin` / `HasProjectPerm` are imported from **`taiga.permissions.permissions`**
- `api.py`: assert the class bases are `ModelCrudViewSet` and `BulkUpdateOrderMixin` in that order; assert the attribute values (`model`, `serializer_class`, `validator_class`, `permission_classes`, `filter_backends`, `filter_fields`, `bulk_update_param`, `bulk_update_perm`, `bulk_update_order_action`); assert a `list` method is defined **and** its body calls `check_permissions` with `"list"` — this is the AC-5 fence and it must fail loudly if someone "simplifies" the override away
- `apps.py`: top-level imports are exactly `["django.apps"]`; `ready()` exists; the registered prefix is `"components"`; `trailing_slash=False`; the appended path prefix is `"api/v1/"`
- `validators.py`: `validate_name` and `validate_project` exist with the **`(self, attrs, source)`** signature (assert the arg names — this is the DRF-2 trap) and each returns `attrs`
- `services.py`: assert it imports no `taiga.*` module. That property is what makes Layer B honest; assert it, do not assume it
- Package file allowlist (replaces the `urls.py` blacklist) — see **File structure**

**B. Django + SQLite (extend `tests/_django_sqlite_harness.py`, `importorskip("django")`)**

- Keep every existing 2.1 assertion passing unchanged
- Add `tests/_taiga_stub` to the child `PYTHONPATH`; after `django.setup()`, assert the shim router recorded a `components` registration bound to `ComponentViewSet` and that `taiga.urls.urlpatterns` grew by one
- Run `services.normalize_name` / `name_conflicts` for real: `"API"` vs `"api"` vs `"  api  "` conflict inside one project; the same name in another project does not; `exclude_pk` lets a rename keep its own name
- Run `bulk_update_component_order` for real: orders update; a component id from another project updates **zero** rows
- Empty and whitespace-only names: assert `normalize_name` yields `""` so the validator's non-empty rule has something to reject

**C. Live container (`skipif` — Docker + a running overlay stack)**

Reuse the `_compose_exec` / `_overlay_exec_available` probe style from `tests/test_components_models.py` (`timeout=` on every `subprocess.run`, skip on `OSError`/`TimeoutExpired`, distinguish "environment absent" from "check failed"):

- Anonymous `GET /api/v1/components?project=<id>` → **401** (AC-5)
- Project-member-non-admin GET → **200** with the catalog (AC-3); POST/PATCH/DELETE/`bulk_update_order` → **403** (AC-4)
- Admin POST duplicate-by-case → **400**, not 500 (AC-1)
- Admin POST with another project's id → **403** (AC-2)
- Admin `DELETE` of a component that has Assignments → **204**, Assignment rows gone, User Story still `GET`-able (AC-6)

Skip honestly when Docker or the stack is absent. Do not start a stack in CI.

### File structure

```text
addons/components/back/taiga_contrib_components/
  __init__.py        # UPDATE — comment only. No Django and no Taiga imports
  apps.py            # UPDATE — + ready() router registration
  models.py          # UNCHANGED
  api.py             # CREATE — ComponentViewSet
  serializers.py     # CREATE — ComponentSerializer
  validators.py      # CREATE — ComponentValidator
  permissions.py     # CREATE — ComponentPermission
  services.py        # CREATE — normalize_name, name_conflicts, bulk_update_component_order
  migrations/        # UNCHANGED
tests/
  test_components_api.py    # CREATE — Layer A + Layer C
  _taiga_stub/taiga/...     # CREATE — import shim for the Layer B child only
  _django_sqlite_harness.py # UPDATE — shim on path, services + registration assertions
  test_plugin_load.py       # UPDATE — two assertions replaced (see Tasks)
platform/UPGRADE.md         # UPDATE — one catalog curl in the smoke glance
docs/implementation/deferred-work.md  # UPDATE
```

**No `urls.py`** — registration lives in `apps.ready()` per the slack idiom. The new package allowlist is exactly: `__init__.py`, `apps.py`, `models.py`, `api.py`, `serializers.py`, `validators.py`, `permissions.py`, `services.py`, `migrations/`.

`platform/back.Dockerfile` needs **no** change: `install-enabled-addons.sh` does `cp -a` of the whole package, so new modules travel for free (1.2).

### Files being modified — current state / change / preserve

| File | Today | This story changes | Must preserve |
| --- | --- | --- | --- |
| `taiga_contrib_components/apps.py` | 5-line `ComponentsConfig`, sole import `django.apps` | Add `ready()` with lazy imports | Exactly one class, `name`, `default = True`, `default_auto_field`; top-level import stays `django.apps` only |
| `taiga_contrib_components/__init__.py` | "Models and migrations only; no URLs or REST yet." | Comment only | **No Django, no Taiga imports** — `test_stub_app_importable_from_repo` imports it bare |
| `taiga_contrib_components/models.py` | `Component`, `Assignment` (2.1) | **Do not change** | `db_constraint=False` on core FKs, `Meta.ordering = ("order", "id")`, `save()` strip, the assignment unique constraint |
| `migrations/0001_initial.py` | 2 `CreateModel` + `RunSQL` index | **Do not change** | No `0002_*` — this story adds no fields. `makemigrations --check` must stay clean |
| `tests/test_plugin_load.py` | 17 passed, 2 skipped | Two assertions replaced (see Tasks) | Every 1.2 invariant: registry parsing, overlay append-not-replace, Dockerfile hook order, front stub manifest |
| `tests/test_components_models.py` | 16 passed, 2 skipped | May gain the shim path | All 2.1 AC assertions, the AC-2 default-deny fence, the `ADDON_TABLES` sync test |
| `tests/_django_sqlite_harness.py` | 2.1 child, exits 0 | Shim on `PYTHONPATH` + new assertions | Every existing assertion, the subprocess-isolation design (D1) |
| `platform/UPGRADE.md` | 1.3 playbook | One curl line in the smoke glance | Ordered needles asserted by `test_upgrade_playbook.py`; the curly-apostrophe line at :5 (see `deferred-work.md`) |
| `platform/*` (everything else) | 1.1–1.3 artifacts | **Do not change** | `TAIGA_PIN` = `6.10.2`, override, Dockerfiles, `overlay.py`, `smoke.py`, `README.md`, `addons.txt` |
| `addons/components/front/*` | 1.2 stub plugin | **Do not change** | Epic 3 owns the front |

**Verified baseline at story creation: `python -m pytest -q` → 80 passed, 6 skipped** (overlay 20/1, plugin_load 17/2, upgrade_playbook 27/1, components_models 16/2).

### Library / framework

- **No new runtime dependency.** Everything comes from the pinned image: `taiga.base.api.*`, `taiga.base.routers`, `taiga.base.filters`, `taiga.base.fields`, `taiga.base.exceptions`, `taiga.permissions.permissions`, `taiga.projects.mixins.ordering`.
- **Forbidden:** `djangorestframework` (Taiga vendors its own fork; installing upstream DRF would shadow nothing and mislead everything), `django-filter`, `drf-nested-routers`, `django-ordered-model`, `psycopg2` in dev, `django.contrib.postgres` fields.
- Dev-only: `pytest`, `PyYAML`, `Django==3.2.25; python_version < "3.13"` — already in `requirements-dev.txt`. Adding a Django major other than 3.2 is the worst available outcome (2.1's warning still stands).

### Out of scope (stop if you start these)

- Any Assignment endpoint, serializer, or validator — **2.3**
- Project-settings UI, picker, chips — **Epic 3**
- The cross-project Assignment invariant decision — **2.3** (see `deferred-work.md`)
- Emitting `taiga.events` on catalog change (no AC asks for it)
- `MoveOnDestroyMixin` / `ArchivedByProjectMixin` / `BlockedByProjectMixin`
- `admin.py`, management commands, data migrations, seed Components
- Extending `platform/smoke.py` — 1.3's contract is stub load; the operator glance goes in `UPGRADE.md`
- Bumping `TAIGA_PIN`, or "fixing" the known `taiga-front:6.10.2` Hub 404
- Anything under `docs/planning/`

### Previous story intelligence

**1.1** (`done`): `platform/TAIGA_PIN` is the declared seed. Honesty protocol (skipif, never fake) starts here.

**1.2** (`done`): Append-not-replace; `install-enabled-addons.sh` `cp -a`s the whole package, so new modules need no Dockerfile edit. Review rule that binds this story hardest: **do not prove one implementation with a second reimplementation of it** — hence the anti-drift guard on `tests/_taiga_stub`.

**1.3** (`done`): Review findings still binding — needle/substring tests over a whole file are an anti-pattern (assert on parsed structure, hence AST over `api.py`); a source grep is not proof of reuse; every `subprocess.run` needs `timeout=`; distinguish "environment absent" from "check failed".

**2.1** (`done`): Established the addon's Django conventions. Its review produced ten patches; the pattern to inherit is **default-deny fences** (the AC-2 migration fence default-denies unknown operations rather than blacklisting known-bad ones). Apply the same instinct to the package file allowlist and the shim symbol set. Its deferred items that are **yours**: FR-6 trimmed/non-empty enforcement, and the file-allowlist replacement for the `urls.py` blacklist. Its deferred items that are **not yours**: Postgres collation vs SQLite `lower()`, `RunSQL` invisibility to `makemigrations --check`, the cross-project Assignment decision.

### Git intelligence

HEAD `38d7f92` — *Mark story 2.1 done after review follow-ups.* Preceding: `8ca0afa` (2.1 implementation), `cffe7d6`/`ccabb48` (1.3), `2dacd08` (1.2).

Rhythm across all four stories: **red tests first → implementation → `python -m pytest -q` as proof → review follow-up commit**. Two commits per story. Working tree stays limited to the story's own files. Branch `master`, clean, ahead of `origin/master`. `__pycache__` is untracked — keep it that way.

### Latest tech information

Verified 2026-08-18 against the `6.10.2` tag:

- `taigaio/taiga-back:6.10.2` `requirements.txt`: `django==3.2.25`, `psycopg2==2.9.11`, `celery==5.5.3`, `gunicorn==23.0.0`. **No `djangorestframework`.**
- `REST_FRAMEWORK` in `settings/common.py`: `DEFAULT_AUTHENTICATION_CLASSES = ("taiga.auth.authentication.JWTAuthentication", "taiga.auth.backends.Session", "taiga.external_apps.auth_backends.Token")`; `EXCEPTION_HANDLER = "taiga.base.exceptions.exception_handler"`; `PAGINATE_BY = 30`.
- `JWTAuthentication.authenticate_header()` returns `'Bearer realm="api"'` — the reason anonymous denials are 401 and not 403.
- `taiga.base.routers` exports only `DefaultRouter` (nested + DRF-default). No module-level router instance exists; each addon creates its own, as slack does.
- Django 3.2 is EOL upstream. Write for 3.2, not for what is current.
- Hub tag reality (unchanged): `taiga-back:6.10.2` exists, `taiga-front:6.10.2` is a 404 — documented in `platform/UPGRADE.md`, not this story's problem.

### References

- [Source: docs/planning/epics.md] Epic 2, Story 2.2; FR coverage map (FR-6…FR-10 → 2.2, 3.1)
- [Source: docs/planning/prd.md:113-158] § 4.2 Component catalog — FR-6 (required, trimmed, non-empty, unique per Project case-insensitive), FR-7, FR-8 (unlink, do not delete stories), FR-9 (project-scoped, display order), FR-10 (admin-only writes, members read, unauthenticated rejected)
- [Source: docs/planning/prd.md:266-270] Testable consequences summary
- [Source: docs/planning/ARCHITECTURE-SPINE.md] AD-6 (addon-owned schema), AD-7 (permissions map to existing Taiga roles), AD-8 (`/api/v1/<slug>/...`, Official Taiga JWT, every write validates project scope), AD-9; Consistency Conventions (integer PKs, ISO-8601, DRF error envelope, logger `taiga_contrib_components`)
- [Source: docs/planning/architecture.md] "Components data" § — permissions table; REST addon-owned under `/api/v1/components/...`
- [Source: docs/planning/ARCHITECTURE-SPINE.md#Deferred] delete-with-assignments is **unlink after confirm**, not 409
- [Source: docs/implementation/2-1-models-and-migrations.md] Model contract, `db_constraint=False` rationale, honesty protocol, Layer A/B/C structure
- [Source: docs/implementation/deferred-work.md] `Component.save()` normalization is not an invariant (FR-6 is 2.2's); file-allowlist item; cross-project Assignment (2.3's)
- [Source: tests/test_plugin_load.py:239-273] The two assertions this story must replace
- [Source: tests/_django_sqlite_harness.py] Layer B child that `ready()` will break without the shim
- Official: https://github.com/taigaio/taiga-contrib-slack/blob/main/back/taiga_contrib_slack/apps.py (router registration in `ready()`)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/projects/api.py (`SeverityViewSet` / `UserStoryStatusViewSet` catalog shape)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/projects/permissions.py (`SeverityPermission` `*_perms`)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/projects/mixins/ordering.py (`BulkUpdateOrderMixin`)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/base/api/mixins.py (`list()` does not check permissions; `create()` validates before checking)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/base/api/views.py (`permission_denied` → 401 vs 403)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/base/filters.py (`CanViewProjectFilterBackend`)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/permissions/services.py (`_get_object_project`)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/taiga/projects/validators.py (`DuplicatedNameInProjectValidator` — the exact-match version ours must improve on)

### Project structure notes

The addon package grows from 3 modules to 8, all inside `taiga_contrib_components/`. No new top-level directory, no change to `platform/addons.txt`, no second compose override (AD-9). `services.py` deliberately holds every rule that can run without Taiga installed — that boundary is the story's main testability decision, and 2.3 should extend it rather than move logic back into the viewset.

### Project context reference

No `project-context.md` in this repo. The governing context is `docs/planning/ARCHITECTURE-SPINE.md` (AD-1…AD-9) plus the 1.1–2.1 review decisions recorded in those story files and `docs/implementation/deferred-work.md`.

## Dev Agent Record

### Agent Model Used

Grok 4.6 (bmad-dev-story)

### Implementation Plan

- Red first: Layer A AST in `tests/test_components_api.py`, Layer B harness + `_taiga_stub` import shim, Layer C `skipif` HTTP. Suite went 10 failed / 79 passed / 8 skipped before addon modules existed.
- Trap fix before `ready()`: `test_plugin_load.py` now asserts top-level `apps.py` imports only `django.apps` and `ready()` imports exactly `{django.urls, taiga.base, taiga.urls, .api}`; package fence is an allowlist. Companion: `test_components_models.py` top-level import check so `ready()` does not break 2.1.
- Green: `services.py` (no `taiga.*`), DRF-2 `ComponentValidator`, exact `ComponentPermission` table, `LightSerializer` without `I18NField`, `ComponentViewSet` with `list()` permission check, slack-idiom `apps.ready()` router (`trailing_slash=False`, `base_name="components"`).
- Deliberately omitted `MoveOnDestroyMixin` / `ArchivedByProjectMixin` / `BlockedByProjectMixin` — no AC requires them.
- Verify: `python -m pytest -q` → **89 passed, 8 skipped**. Live HTTP skipif (Docker absent). `platform/smoke.py` untouched.

### Debug Log References

- RED: 10 failed, 79 passed, 8 skipped (`test_stub_app_importable_from_repo` allowlist + new Layer A + harness import of missing `services` / `ready()` registration). Two new Layer C tests skipped (Docker absent).
- GREEN after implementation: two leftover assertion mismatches — services relative `.models` import (test expected only `django.db`) and stub helper class `_Perm` counted as an extra symbol. Fixed the assertion and inlined stub permission dunders.
- GREEN: `python -m pytest -q` → **89 passed, 8 skipped**.
- Live `docker compose exec` HTTP was **not** executed — Docker absent. Layer A/B ran. skipif is honest.
- Review follow-up GREEN: `python -m pytest -q` → **90 passed, 8 skipped** (one new `UPGRADE.md` glance needle). Live HTTP still skipif.

### Completion Notes List

- Catalog REST is addon-owned under `/api/v1/components` (slashless). `apps.ready()` registers `DefaultRouter(trailing_slash=False)` with `base_name="components"` using only lazy imports. `__init__.py` still imports nothing.
- AC-1 uniqueness (trimmed, case-insensitive) is enforced in `ComponentValidator.validate_name` via `services.normalize_name` + `services.name_conflicts` (`name__iexact`). Empty/whitespace-only names 400. The 2.1 unique index remains the 500-backstop.
- AC-2: `validate_project` rejects changing `project` on update. `bulk_update_component_order` predicates on `project_id=project.id` so a foreign id updates zero rows. Filter backend + `filter_fields = ("project",)` is the list/retrieve scoping path (HTTP proof is Layer C).
- AC-3/4/5 are **not** proven live. Layer A asserts the exact `*_perms` table and that `list()` calls `check_permissions(..., "list", ...)`. Layer C HTTP 200/403/401 is skipif. Recorded in deferred-work.
- AC-5 consequence implemented as written: anonymous list/retrieve is 401 (`IsAuthenticated` on `list_perms`/`retrieve_perms`). A public project viewed logged-out therefore diverges from official catalogs (200). 3.3 must revisit if chips need anonymous public rendering.
- AC-6 unlink is the existing `Assignment.component` CASCADE. No manual `Assignment.objects.filter(...).delete()` in `destroy`. API-path proof is Layer C skipif; model-path proof remains the 2.1 harness.
- `services.py` imports only `django.db` + `.models`. Reorder is ORM `QuerySet.update`, not raw Postgres.
- Official mixins not added: `MoveOnDestroyMixin`, `ArchivedByProjectMixin`, `BlockedByProjectMixin` — none required by an AC.
- File-allowlist deferred item resolved. `platform/smoke.py` not touched. One authenticated catalog curl added to `platform/UPGRADE.md`. The pre-2.2 line telling operators not to curl the catalog until Epic 2 ships REST was removed (it is now false); Completion Notes previously mentioned only the addition.
- ✅ Resolved review finding [Patch]: malformed `bulk_components` is 400 via `api.bulk_update_component_order` wrapper; `services.py` stays `taiga.*`-free. Layer B executes the ValidationError path.
- ✅ Resolved review finding [Patch]: anti-drift now symbol-checks stub modules reached as imported names (`taiga.base.routers` et al.).
- ✅ Resolved review finding [Patch]: Layer C skip only on pre-flight probe; in-stack exceptions and missing AC-6 output fail.
- ✅ Resolved review finding [Patch]: live users get a per-run `secrets.token_urlsafe` password.
- ✅ Resolved review finding [Patch]: ADMIN_OTHER 201 ids are appended to cleanup.
- ✅ Resolved review finding [Patch]: catalog glance derives `TAIGA_URL` from sourced `TAIGA_SCHEME`/`TAIGA_DOMAIN` and fails closed on non-200.
- ✅ Resolved review finding [Patch]: ViewSet assigns default-deny; `list` must `return super().list(...)`; serializer field ctor last name is exactly `Field`.
- ✅ Resolved review finding [Patch]: harness measures `urlpatterns` growth across `django.setup()`.
- ✅ Resolved review finding [Patch]: `ALLOWED_STUB_APP_ENTRIES` lives in `tests/_addon_package.py`; urls.py blacklist line removed.
- ✅ Resolved review finding [Patch]: deferred-work titles AC-1/AC-2 as unproven live and records the anonymous write 404 and any-authenticated-list narrowings.
- ✅ Resolved review finding [Patch]: `UPGRADE.md` "do not curl until Epic 2" deletion recorded here.

### File List

- addons/components/back/taiga_contrib_components/__init__.py
- addons/components/back/taiga_contrib_components/apps.py
- addons/components/back/taiga_contrib_components/api.py
- addons/components/back/taiga_contrib_components/permissions.py
- addons/components/back/taiga_contrib_components/serializers.py
- addons/components/back/taiga_contrib_components/services.py
- addons/components/back/taiga_contrib_components/validators.py
- tests/test_components_api.py
- tests/test_components_models.py
- tests/test_plugin_load.py
- tests/test_upgrade_playbook.py
- tests/_addon_package.py
- tests/_django_sqlite_harness.py
- tests/_taiga_stub/taiga/__init__.py
- tests/_taiga_stub/taiga/urls.py
- tests/_taiga_stub/taiga/base/__init__.py
- tests/_taiga_stub/taiga/base/routers.py
- tests/_taiga_stub/taiga/base/filters.py
- tests/_taiga_stub/taiga/base/exceptions.py
- tests/_taiga_stub/taiga/base/fields.py
- tests/_taiga_stub/taiga/base/api/__init__.py
- tests/_taiga_stub/taiga/base/api/viewsets.py
- tests/_taiga_stub/taiga/base/api/permissions.py
- tests/_taiga_stub/taiga/base/api/validators.py
- tests/_taiga_stub/taiga/base/api/serializers.py
- tests/_taiga_stub/taiga/permissions/__init__.py
- tests/_taiga_stub/taiga/permissions/permissions.py
- tests/_taiga_stub/taiga/projects/__init__.py
- tests/_taiga_stub/taiga/projects/mixins/__init__.py
- tests/_taiga_stub/taiga/projects/mixins/ordering.py
- platform/UPGRADE.md
- docs/implementation/deferred-work.md
- docs/implementation/2-2-catalog-rest-and-permissions.md
- docs/implementation/sprint-status.yaml

### Change Log

- 2026-08-18: Story created (ready-for-dev).
- 2026-08-18: Implemented catalog REST + permissions (services, DRF-2 validator, viewset, slack-idiom router). Layer A/B green. Live HTTP skipif. Status → review.
- 2026-08-18: Addressed code review findings - 11 items resolved (Date: 2026-08-18). Reorder payload 400 wrapper, stub name-module symbol check, fail-closed Layer C, random live password, ADMIN_OTHER cleanup, UPGRADE.md URL + http_code, ViewSet default-deny, urlpatterns growth, single allowlist, deferred-work honesty, recorded UPGRADE.md deletion. Suite 90 passed, 8 skipped. Status → review.
- 2026-08-19: Marked done after review follow-ups.

### Review Findings

Code review 2026-08-18. Three parallel layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) plus an independent pass. Suite re-verified: **89 passed, 8 skipped**.

- [x] [Review][Patch] **Malformed `bulk_components` payload 500s instead of 400** — `for component_id, order in data` unpacks request data with no shape check. `{"bulk_components": [[7]]}`, `[[7,1,9]]`, `["x"]`, or `[[7,"abc"]]` raise `ValueError`/`TypeError`/`DataError` from an admin-reachable endpoint; `BulkUpdateOrderMixin` validates only that the two keys exist. **Resolved 2026-08-18 — approach (a) chosen:** validate in `api.py`, keep `services.py` free of `taiga.*`. Add a module-level `bulk_update_component_order(project, user, data)` wrapper in `api.py` that rejects a non-sequence payload, non-pair elements, and non-integer ids/orders with `taiga.base.exceptions.ValidationError` (400), then delegates to the pure `services.bulk_update_component_order`. Point `bulk_update_order_action` at the wrapper. **Do not override the mixin's `bulk_update_order` method** — the route is discovered from a `@list_route` decorator's attributes, so an override without re-applying it would silently unregister the endpoint. **Deviation from spec:** § ViewSet shape mandates `bulk_update_order_action = services.bulk_update_component_order`; the wrapper keeps the same name and 3-arg plain-function shape (no `staticmethod`, no `self`) so the existing Layer A assertion still holds, but the target module changes. Upside: the stub already provides a real `ValidationError`, so this is the first reorder rule Layer B can execute rather than merely parse — add that assertion. [addons/components/back/taiga_contrib_components/services.py:24, addons/components/back/taiga_contrib_components/api.py:21]

- [x] [Review][Patch] **Anti-drift guard does not symbol-check the stub modules reached as names** — `test_taiga_stub_matches_addon_imports_exactly` runs `_stub_defined_names` / `extra = defined - names` only for modules that are *keys* of `EXPECTED_TAIGA_IMPORTS`. `taiga.base.routers`, `taiga.base.filters`, `taiga.base.api.validators`, `taiga.base.api.serializers` are reached only as *names* and are never symbol-checked. Empirically verified: appending a `SneakySecondImplementation` class to `_taiga_stub/taiga/base/routers.py` leaves the suite at 89 passed. `routers.py` is the one stub carrying state and logic (`instances`, `registry`, `register()`) — exactly what the guard exists to fence, and exactly the 1.2 rule "do not prove one implementation with a second reimplementation of it". [tests/test_components_api.py:412]

- [x] [Review][Patch] **Layer C live tests convert genuine check failures into skips** — the whole in-container body is wrapped in `except Exception: print("ERROR:...")` and the parent does `if "ERROR:" in out: pytest.skip(...)`. `auth_header()` has no `HTTPError` handling, so a broken login, a changed `Membership` signature, a permission class raising, or the viewset 500ing all report as *skipped*. AC-6 is doubly fail-open via its own `except Exception: print("DELETE_CASCADE:SKIP:...")` plus `if "DELETE_CASCADE:SKIP" not in out`. Same shape in `test_live_anonymous_catalog_list_is_401`. Hardcoded `settings.overlay` and `127.0.0.1:8000` mean a misconfigured stack also vanishes rather than failing. This violates the 1.3 binding rule the spec restates ("distinguish environment absent from check failed") in the only tests that can prove AC-3/4/5/6. Fix: skip only on the pre-flight probe; once the stack answers, any exception is a failure. [tests/test_components_api.py:499, 690]

- [x] [Review][Patch] **Live test creates project admins with a hardcoded password and best-effort cleanup** — `user.set_password("catalog-22")` plus `Membership.objects.create(..., is_admin=True)`, cleaned up in a `finally` *inside a subprocess*. A `docker compose exec` timeout, container restart, or SIGKILL leaves `c22admin<hex>` as a real project admin with a publicly-known password. `TAIGA_DOCKER` points at whatever stack the operator has; nothing restricts this to a throwaway. Use a per-run random password. [tests/test_components_api.py:558]

- [x] [Review][Patch] **Live test leaks a component row on the exact failure it hunts for** — in the `ADMIN_OTHER` block the response id is never appended to `created_component_ids`, so if the cross-project POST wrongly returns 201 the `finally` block leaves a permanent row in the operator's database while the test reports failure. [tests/test_components_api.py:648]

- [x] [Review][Patch] **`UPGRADE.md` catalog glance uses an undefined variable and cannot fail** — `$TAIGA_URL` is defined nowhere in the repo (verified: it is the file's only occurrence), so the documented command requests `/api/v1/components?project=<id>` against an empty host. The surrounding playbook is careful about exactly this (it explains sourcing `.env` for `TAIGA_ADDONS_ROOT`). Separately, `curl -sS` without `-f` or a `%{http_code}` write-out exits 0 on 401/403/404/500 alike, so an operator sees a clean run while the endpoint is unregistered. [platform/UPGRADE.md:163-169]

- [x] [Review][Patch] **`api.py` shape test has no default-deny fence** — `test_permissions_perms_table_and_import_sources` correctly asserts `extra == set()`; `test_api_viewset_shape_and_list_checks_permissions` asserts only that nine named attributes are present, so an added attribute (a hand-rolled `queryset`, a re-added mixin flag) draws no objection. The spec names default-deny fences as the pattern to inherit from 2.1. Also: the `list` test never asserts `return super().list(...)`, so deleting that line keeps the AC-5 fence green while breaking `list` entirely; and `_attr_path(call.func).endswith("Field")` would accept `I18NField`, which the spec explicitly prohibits (caught only indirectly, by the anti-drift import set). [tests/test_components_api.py:300, 391]

- [x] [Review][Patch] **Harness asserts an absolute count, not growth** — spec section Testing requirements B says assert `taiga.urls.urlpatterns` *grew by one*; `assert len(urlpatterns) == 1` is equivalent only because the stub seeds `urlpatterns = []`. It measures the stub's initial state rather than `ready()`'s effect and would not detect a double registration if the stub is ever seeded. [tests/_django_sqlite_harness.py:80]

- [x] [Review][Patch] **The package allowlist is duplicated as two independent constants** — identical `ALLOWED_STUB_APP_ENTRIES` sets in `tests/test_plugin_load.py:31` and `tests/test_components_api.py:27`, with no single source of truth; `deferred-work.md` cites both as the resolution. A future story that adds a module and updates one file gets a red suite pointing at the wrong place. `test_package_file_allowlist` also still carries the superseded `assert not (STUB_APP / "urls.py").exists()` blacklist line the allowlist replaced. [tests/test_components_api.py:27, tests/test_plugin_load.py:31]

- [x] [Review][Patch] **Completion record understates what went unproven live** — the new `deferred-work.md` entry is titled "AC-3 / AC-4 / AC-5 / AC-6 live HTTP was not executed", but the skipped `test_live_catalog_member_admin_and_delete_cascade` also carries the only proof of **AC-1** (`ADMIN_DUP:400` — duplicate-by-case returning 400 not 500, which the spec calls "what AC-1 is really guarding") and of **AC-2** (`ADMIN_OTHER:403`). Both are stated unqualified in Completion Notes. Two further unrecorded narrowings: anonymous `PATCH`/`DELETE` on a private project return **404, not 401** (the filter backend hides the row before permissions run), so AC-5's 401 holds only for `list`/`retrieve`/`bulk_update_order`; and `list_perms = IsAuthenticated()` grants 200 to *any* authenticated user, not only members as AC-3 words it. The opposite consequence (anonymous 401 on a public project) was documented carefully — these deserve the same. [docs/implementation/deferred-work.md:57]

- [x] [Review][Patch] **`UPGRADE.md` deletion not recorded** — the patch removes the line telling operators not to curl the catalog until Epic 2 ships REST. The removal is correct (the line is now false) and no `test_upgrade_playbook.py` needle covers it, but the spec scoped this file to "one curl line" and Completion Notes mention only the addition. [platform/UPGRADE.md:181]

- [x] [Review][Defer] **`__iexact` and the `lower(name)` index fold differently, and check-then-insert is unlocked** [addons/components/back/taiga_contrib_components/services.py:15] — deferred, pre-existing category
- [x] [Review][Defer] **`normalize_name` is trim-only — internal whitespace, Unicode NFC/NFD, and zero-width characters all defeat FR-6's intent** [addons/components/back/taiga_contrib_components/services.py:6-9] — deferred, spec defines "trimmed" as strip
- [x] [Review][Defer] **Reorder returns 204 when it matched zero rows; payload is unbounded and unlocked** [addons/components/back/taiga_contrib_components/services.py:24-26] — deferred, spec mandates the silent zero-row guard
- [x] [Review][Defer] **`ready()` append is non-idempotent, invalidates no URL cache, and is sensitive to `INSTALLED_APPS` order** [addons/components/back/taiga_contrib_components/apps.py:16-18] — deferred, spec mandates the verbatim slack idiom
- [x] [Review][Defer] **`GET /api/v1/components` without `?project=` returns interleaved rows from every visible project** [addons/components/back/taiga_contrib_components/api.py:18] — deferred, matches official catalog behaviour
- [x] [Review][Defer] **Validator has an untested fail-open branch and two unverified DRF-2 assumptions** [addons/components/back/taiga_contrib_components/validators.py:15-26] — deferred, needs a real Taiga stack
- [x] [Review][Defer] **Stub `__and__` returns `self`, silently neutering permission expressions** [tests/_taiga_stub/taiga/base/api/permissions.py:9] — deferred, trap for 2.3
- [x] [Review][Defer] **`bulk_update_perm = "change_component"` is not a registered Taiga permission** [addons/components/back/taiga_contrib_components/api.py:20] — deferred, spec mandates setting it
- [x] [Review][Defer] **No logger in any of the five new modules despite the ARCHITECTURE-SPINE convention** [addons/components/back/taiga_contrib_components/] — deferred, no AC covers it
- [x] [Review][Defer] **`test_addon_does_not_reference_taiga_stub` is a substring grep, the anti-pattern 1.3 banned** [tests/test_components_api.py:438] — deferred, low value to rewrite now
