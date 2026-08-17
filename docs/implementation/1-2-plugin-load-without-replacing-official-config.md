---
baseline_commit: ab0f10d3dbd7360ad87198ace1581a0eeab6325a
---

# Story 1.2: Plugin load without replacing official config

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As an operator,
I want Addon Django apps and front plugins appended to official generated config,
so that my existing `.env` URLs and flags keep working.

## Acceptance Criteria

1. **Given** official back config generated from env **When** the overlay back container starts **Then** `INSTALLED_APPS` includes each slug from `platform/addons.txt` as `taiga_contrib_<slug>` **And** official env-driven settings (domain, secret, email, Slack/GitHub flags, etc.) are still in effect.

2. **Given** official front `conf.json` generated from env **When** the overlay front container starts **Then** `contribPlugins` includes `plugins/<slug>/<slug>.json` for each enabled slug **And** official `api` / `eventsUrl` / `baseHref` are unchanged.

3. **Given** a stub `addons/components` back app and front plugin (no domain logic) **When** I inspect running containers **Then** the stub app is importable as `taiga_contrib_components` **And** stub plugin files exist under `/usr/share/nginx/html/plugins/components/`.

## Tasks / Subtasks

- [x] Registry + stub Addon (AC: 1, 3)
  - [x] Create `platform/addons.txt` with slug `components` (comments + blank lines allowed; ignore `#` tails)
  - [x] Replace empty `addons/components/back/.gitkeep` with a minimal importable Django app `taiga_contrib_components` (`__init__.py` + `AppConfig`, **no** models / URLs / REST)
  - [x] Replace empty `addons/components/front/.gitkeep` with stub plugin files: `components.json` + no-op `components.js` (Angular module `taigaContrib.components` — **never** `taigaComponents`)
- [x] Back overlay: append `INSTALLED_APPS`, do not replace `config.py` (AC: 1, 3)
  - [x] `COPY` `addons.txt` + stub package into `platform/back.Dockerfile` **after** the post-`FROM` `ARG TAIGA_PIN`
  - [x] Make the package importable inside `/opt/venv` (`pip install` the stub **or** `COPY` onto `PYTHONPATH` / `/taiga-back/`)
  - [x] Apply `INSTALLED_APPS += ["taiga_contrib_<slug>", ...]` via a **settings overlay module** (`DJANGO_SETTINGS_MODULE=settings.overlay` that `from .config import *` then appends). Bake the `ENV` into the image so **taiga-async** sees the same apps without a compose entrypoint change
  - [x] Keep spine file `platform/entrypoint-back.sh` if used; it must `exec` official `/taiga-back/docker/entrypoint.sh` **after** settings are in effect (official script still runs `migrate` → `loaddata` → gunicorn)
  - [x] Do **not** `COPY` or volume-map a full `config.py`
- [x] Front overlay: append `contribPlugins`, do not replace `conf.json` (AC: 2, 3)
  - [x] `COPY` stub plugin to `/usr/share/nginx/html/plugins/components/`
  - [x] Install a **later** hook than official `30_config_env_subst.sh` (e.g. `/docker-entrypoint.d/40_patch-front-conf.sh` sourced from `platform/patch-front-conf.sh`)
  - [x] After official `conf.json` exists, append each `plugins/<slug>/<slug>.json` with `jq` (add `jq` via `apk`); leave `api` / `eventsUrl` / `baseHref` / official Slack-GitHub entries untouched
  - [x] Idempotent: restart must not duplicate plugin paths
  - [x] Do **not** `COPY` or volume-map a full `conf.json`
- [x] Operator docs + 1.1 test rework (AC: 1–3)
  - [x] Extend `platform/README.md` with the append-not-replace contract; keep every 1.1 README needle
  - [x] Rework `test_override_does_not_replace_official_config_files` so it asserts **no volume maps / no full-file replace**, not a whole-file substring ban (see deferred-work)
  - [x] Update `test_addon_tree_placeholders_exist` to assert real stub files (not only `.gitkeep`)
  - [x] Add `tests/test_plugin_load.py` for registry parsing, overlay-import-then-append, front JSON mutate, Dockerfile COPY/hook order
- [x] Verify (AC: 3)
  - [x] `python -m pytest -q` — 1.1 suite still green plus new plugin-load tests
  - [ ] If Docker is present: build overlay images and assert import + plugin path + `conf.json` keys. If Docker is absent: skip live inspect honestly (1.3 owns smoke). Do **not** fake a live stack

### Review Findings

Code review 2026-08-17 — 3 layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor).

- [x] [Review][Patch] **`addons.txt` is a half-registry — Dockerfiles hardcode the `components` slug (AD-9)** [platform/back.Dockerfile, platform/front.Dockerfile] — `back.Dockerfile` COPYs `addons/components/back/taiga_contrib_components` and `front.Dockerfile` COPYs `addons/components/front/` by literal path. Adding a second slug to `platform/addons.txt` appends `taiga_contrib_<slug>` to `INSTALLED_APPS` for a package never copied into the image → `ModuleNotFoundError` at settings import in **both** `taiga-back` and `taiga-async`, plus a `contribPlugins` entry pointing at a 404. AD-9 says one Addon = tree + **one line** in `addons.txt`. **Decision (Forza, 2026-08-17): option (a) — generalize now.** COPY the whole `addons/` tree and fan out per enabled slug at build time so `addons.txt` is genuinely the single enable switch.

- [x] [Review][Patch] **`mktemp` + `mv` leaves `conf.json` mode 0600 root-owned — nginx workers get 403 and the front never boots** [platform/patch-front-conf.sh]
- [x] [Review][Patch] **`jq unique` sorts, reordering official `contribPlugins`; the script's own test asserts the opposite order and is red on any machine with `jq`** [platform/patch-front-conf.sh + tests/test_plugin_load.py::test_front_patch_script_mutates_fixture_conf]
- [x] [Review][Patch] **No `.gitattributes` with `core.autocrlf=true` — new `.sh` files get CRLF on checkout, breaking `#!/bin/sh` in-container** [.gitattributes (missing), platform/patch-front-conf.sh, platform/entrypoint-back.sh]
- [x] [Review][Patch] **The only *passing* front-patch test models a Python re-implementation whose semantics differ from the shipped script** [tests/test_plugin_load.py::_append_contrib_plugins] — same anti-pattern 1.1 rejected for the fake compose merge; Completion Notes overstate it as proof.
- [x] [Review][Patch] **`overlay.py` fails open: `if __name__ == "settings.overlay"` makes the star-import a silent no-op under any other module name** [platform/overlay.py]
- [x] [Review][Patch] **Reworked override test narrowed too far — only inspects `volumes`, so a `command`/`environment` setting `DJANGO_SETTINGS_MODULE=settings.config` would disable every addon and still pass** [tests/test_overlay_scaffolding.py::test_override_does_not_replace_official_config_files]
- [x] [Review][Patch] **Slug values are never validated before flowing into a Python import path and a filesystem path** [platform/overlay.py, platform/patch-front-conf.sh]
- [x] [Review][Patch] **Vacuous assertion — right-hand side of the `or` is always true** [tests/test_plugin_load.py:117]
- [x] [Review][Patch] **`entrypoint-back.sh` is COPYed + chmod'ed into the image but never referenced — dead artifact that re-invites the AD-4 trap** [platform/back.Dockerfile]
- [x] [Review][Patch] **Brittle substring asserts (`"models"`/`"url" not in apps_src.lower()`) — the anti-pattern the ledger just retired** [tests/test_plugin_load.py:163-164]
- [x] [Review][Patch] **Test deletes every `settings*` entry from `sys.modules` without restoring — order-dependent failures** [tests/test_plugin_load.py:83-86]
- [x] [Review][Patch] **Missing `addons.txt` raises a bare `FileNotFoundError` at Django settings import with no diagnostic** [platform/overlay.py]

- [x] [Review][Defer] **`apk add --no-cache jq` is unpinned and adds a build-time network dependency** [platform/front.Dockerfile] — deferred, pre-existing tension with pin discipline

Dismissed as noise (7): status→`review` while AC-3 unverified (this is exactly the spec's prescribed honesty protocol — subtask left unchecked, ledger entry added); `AppConfig.default = True` / Django-version speculation; `svc or {}` guard for a service that does not exist; hypothetical future official hook numbered >40; hardcoded `/opt/venv/bin/python` in the pin-scoped live test; `.gitkeep` removal losing empty-dir tracking (dirs now hold real files, and the spec required the replacement); missing-file guard around `exec` of the official entrypoint.

## Dev Notes

This story proves **FR-3 / NFR-2 / AD-3 / AD-5 / AD-9**: Addon load through official extension points. No Components domain (models, REST, picker, chips). No `UPGRADE.md` (that is **1.3**).

**Completion honesty:** AC-3 (“inspect running containers”) is **not** satisfied by reading Dockerfiles. If Docker is absent, leave the live subtask unchecked, `skipif` the live test, and record it in Debug Log / deferred-work (same as 1.1 → 1.3). Static tests may prove the files and scripts; they may not claim a running container.

### Canonical paths (use these, do not invent)

| Role | Path |
| --- | --- |
| Enabled slugs (repo + both images) | `platform/addons.txt` → `/opt/taiga-addons/addons.txt` |
| Official back settings (do not overwrite) | `/taiga-back/settings/config.py` |
| Overlay settings module (NEW) | `/taiga-back/settings/overlay.py` with `ENV DJANGO_SETTINGS_MODULE=settings.overlay` |
| Official API entrypoint (exec this) | `/taiga-back/docker/entrypoint.sh` |
| Official async entrypoint (do not replace in compose) | `/taiga-back/docker/async_entrypoint.sh` |
| Official front conf (mutate, do not replace) | `/usr/share/nginx/html/conf.json` |
| Official front generator | `/docker-entrypoint.d/30_config_env_subst.sh` |
| Overlay front append hook | `/docker-entrypoint.d/40_patch-front-conf.sh` (from `platform/patch-front-conf.sh`) |
| Stub plugin dest | `/usr/share/nginx/html/plugins/components/{components.json,components.js}` |
| Official Python | `/opt/venv` (`PATH` already set in the back image) |

### Critical official facts (do not invent a generator)

Official back **6.10.2** does **not** generate `config.py` at container start.

- Image build: `cp docker/config.py settings/config.py`
- Runtime path: `/taiga-back/settings/config.py`
- `DJANGO_SETTINGS_MODULE=settings.config`
- That file **reads env at Django import** (`TAIGA_SECRET_KEY`, `TAIGA_SITES_*`, email, Slack/GitHub `INSTALLED_APPS +=`, etc.)
- `ENTRYPOINT ["./docker/entrypoint.sh"]` = `migrate` → `loaddata initial_project_templates` → `chown` → gunicorn
- Source: https://github.com/taigaio/taiga-back/blob/6.10.2/docker/entrypoint.sh and `docker/config.py`

Official front **6.10.2** (`FROM nginx:1.23-alpine`) **does** generate `conf.json` at start:

- `/docker-entrypoint.d/30_config_env_subst.sh` builds `CONTRIB_PLUGINS` from `ENABLE_SLACK` / GitHub / GitLab, then `envsubst` **only if** `/usr/share/nginx/html/conf.json` is missing
- Template keys: `api` = `${TAIGA_URL}${TAIGA_SUBPATH}/api/v1/`, `eventsUrl` = `${TAIGA_WEBSOCKETS_URL}${TAIGA_SUBPATH}/events`, `baseHref` = `${TAIGA_SUBPATH}/`
- Static root: `/usr/share/nginx/html/`
- Source: https://github.com/taigaio/taiga-front/blob/6.10.2/docker/config_env_subst.sh

Official compose (do not fight):

- `taiga-async` **replaces** image `ENTRYPOINT` with `/taiga-back/docker/async_entrypoint.sh` (Celery only — **no** migrate)
- Commented advanced volumes `./config.py:/taiga-back/settings/config.py` and `./conf.json:/usr/share/nginx/html/conf.json` **ignore env**. Overlay default must not enable them
- Source: https://github.com/taigaio/taiga-docker/blob/stable/docker-compose.yml

### AD-4 trap — highest implementation risk

If you only wrap the **image** `ENTRYPOINT` to mutate `config.py` at start:

- `taiga-back` runs the wrapper → apps appended
- `taiga-async` official compose **overrides** entrypoint → wrapper never runs
- `test_override_does_not_touch_async_entrypoint` **forbids** fixing that in the override
- The two processes do **not** share `settings/` (only `static` + `media` volumes)

**Required solution:** bake the append so both processes see it **without** changing compose async entrypoint.

**Do this (recommended):**

```python
# /taiga-back/settings/overlay.py  (NEW file — do not overwrite config.py)
from .config import *  # official env-driven settings stay

# read /opt/taiga-addons/addons.txt (copied at build); skip blanks and # comments
# for each slug: INSTALLED_APPS += [f"taiga_contrib_{slug}"] if not already present
```

```dockerfile
ENV DJANGO_SETTINGS_MODULE=settings.overlay
# leave official ENTRYPOINT ["./docker/entrypoint.sh"]
```

This also covers `taiga-manage` / `entrypoint: python manage.py`, which skip wrappers.

**Do not** replace official `async_entrypoint.sh` with the API entrypoint (that would gunicorn in the worker).

If you still ship `platform/entrypoint-back.sh` (spine name), it may only `exec` official `/taiga-back/docker/entrypoint.sh "$@"`. Runtime mutate of `config.py` is acceptable **only if** it is idempotent **and** async still sees the apps (overlay settings module or in-image wrap of **both** official scripts). Prefer the settings module.

### Front hook order

Official nginx runs `/docker-entrypoint.d/*.sh` in lexical order **before** nginx.

1. Official `30_config_env_subst.sh` writes `conf.json` from env (if missing)
2. Overlay `40_…` (from `platform/patch-front-conf.sh`) **mutates** `contribPlugins` only

A `10_` / `20_` hook runs too early. Replacing `30_` forks official Slack/GitHub flags.

`jq` is not in the official front image — `apk add --no-cache jq` in `front.Dockerfile`. Front has **no** Python.

Sketch:

```bash
# after official 30_ has run
CONF=/usr/share/nginx/html/conf.json
# fail loudly if missing
# for each slug in addons.txt:
#   jq --arg p "plugins/${slug}/${slug}.json" \
#     '.contribPlugins = ((.contribPlugins // []) + [$p] | unique)'
```

Do not rewrite `api`, `eventsUrl`, `baseHref`. Do not bake a static `conf.json` into the image.

### Stub shapes (copy these, do not invent Slack)

Back (enough for `INSTALLED_APPS`; no `ready()` URL hook — that is Epic 2):

```
addons/components/back/taiga_contrib_components/
  __init__.py
  apps.py          # AppConfig.name = "taiga_contrib_components"
# optional setup.cfg / pyproject.toml only if you pip install
```

Front (official Slack flattens `front/dist/*` into `plugins/<slug>/`):

```
addons/components/front/
  components.json
  components.js
```

`components.json` (Slack shape; **no admin UI in this story**):

```json
{
  "name": "Components",
  "slug": "components",
  "description": "Components addon stub",
  "type": "misc",
  "module": "taigaContrib.components",
  "js": "plugins/components/components.js"
}
```

Use a type that is **not** `admin` / `auth` / `userSettings` so official front does not add a settings route to an empty plugin. If the pinned front refuses unknown types, use `admin` **and** ship a one-line placeholder template — still no catalog UI (3.1).

`components.js` must define the Angular module named in the JSON:

```javascript
(function () {
  "use strict";
  angular.module("taigaContrib.components", []);
})();
```

**Never** name the module `taigaComponents` — that is already a **core** Taiga module.

### Files being modified — current state / change / preserve

| File | Today | This story changes | Must preserve |
| --- | --- | --- | --- |
| `platform/back.Dockerfile` | Pin + `FROM taigaio/taiga-back:${TAIGA_PIN}` + post-`FROM` `ARG` only | COPY addons, install stub, settings overlay `ENV` | Pin `ARG` defaults = `TAIGA_PIN`; no `:latest`; second `ARG` before any `${TAIGA_PIN}` use |
| `platform/front.Dockerfile` | Same skeleton for front | COPY plugin + `40_` hook; `apk add jq` | Same pin/`FROM`/`ARG` rules; official `30_` left in place |
| `platform/docker-compose.override.yml` | Image swap only; async has no `entrypoint`/`command`/`build` | **Prefer no change.** Never add `config.py` / `conf.json` volumes | Only back/async/front; same back/async image; `pull_policy: never`; `TAIGA_ADDONS_ROOT` context |
| `platform/README.md` | Attach path; last line defers plugin load to 1.2 | Document append-not-replace + `addons.txt` | All needles in `test_readme_documents_attach_and_pin` |
| `tests/test_overlay_scaffolding.py` | 20 passed, 1 skipped (no Docker) | Rework substring test; update `.gitkeep` assert | All other 1.1 invariants |
| `addons/components/{back,front}/.gitkeep` | Empty placeholders | Replace with stub package / plugin files | Tree stays `addons/<slug>/{back,front}` |
| `platform/TAIGA_PIN` | `6.10.2` | **Do not change** | Single declared seed |
| `platform/compose.env.example` | Two append-only keys | **Leave** (no new env required) | `TAIGA_ADDONS_ROOT=` + `TAIGA_PIN=<pin>` |
| `.dockerignore` | Excludes `_bmad`, `docs`, `tests`, caches | **Leave** unless you accidentally exclude `addons/` or `platform/` | `platform/` and `addons/` must remain in build context |

### Architecture compliance (must follow)

- **AD-1** No vendor/fork of `taiga-back` / `taiga-front` / `taiga-docker`.
- **AD-2** Pin stays `6.10.2` unless the operator already overrode it. No `:latest`.
- **AD-3** Append official config; never replace it. No default volume of full `config.py` / `conf.json`.
- **AD-4** Same overlay back image for `taiga-back` and `taiga-async`. Same `INSTALLED_APPS`. Official `migrate` stays on the API entrypoint.
- **AD-5** Runtime contrib plugin only. Do **not** start a front-from-source rebuild.
- **AD-9** One Addon = `addons/<slug>/{back,front}` + one line in `platform/addons.txt`.

### Out of scope (stop if you start these)

- `platform/UPGRADE.md` and live login smoke → **1.3**
- Component models, migrations, REST → **2.x**
- Project settings UI, story picker, chips → **3.x**
- New compose services, Kubernetes, custom gateway
- Changing `TAIGA_PIN`, official `.env` keys, or async Celery flags (`-B`, concurrency)

### Testing requirements

Reuse `requirements-dev.txt` (`pytest`, `PyYAML`). No new runtime language.

**1.1 tests you will break if careless**

- `test_override_does_not_replace_official_config_files` (lines 148–153) fails if the **override YAML text** contains `config.py`, `conf.json`, `INSTALLED_APPS`, or `contribPlugins` **anywhere**, including comments. **Rework it** to: override services have no `volumes` mapping those files; no `entrypoint`/`command` on async. Putting those strings in Dockerfiles/scripts is fine.
- `test_addon_tree_placeholders_exist` fails if `.gitkeep` is deleted without updating the test.
- Dockerfile pin / `FROM` / post-`FROM` `ARG` tests still apply after you add `COPY` lines.
- README needle test still applies.

**New tests (`tests/test_plugin_load.py`)**

- `addons.txt` parser: `components` → `taiga_contrib_components` and `plugins/components/components.json`; comments/blanks ignored
- Back Dockerfile `COPY`s addons + overlay; sets `DJANGO_SETTINGS_MODULE=settings.overlay` (or equivalent baked append); does **not** `COPY` a full `config.py`
- Front Dockerfile copies plugin dest `.../plugins/components/` and a `docker-entrypoint.d/40*` (or later) script; does **not** `COPY` a full `conf.json`
- Settings overlay source `from .config import *` (or `from settings.config import *`) **before** any `INSTALLED_APPS +=`
- Front patch script uses `jq` on existing `conf.json` and does not `envsubst` a replacement file
- Stub `taiga_contrib_components` is importable from repo with `PYTHONPATH=addons/components/back`
- Stub plugin files exist in repo
- Unit-test the front patch against a **fixture** `conf.json` that already has `api`/`eventsUrl`/`baseHref` and maybe `"plugins/slack/slack.json"` — after patch, URLs identical, both plugin paths present, no dupes on second run

Live container inspect is **optional** (`skipif` no Docker), same honesty as 1.1. 1.3 owns the smoke script.

### Library / framework

- No new app runtime. Official image Pythons/Django/AngularJS/nginx stay as shipped.
- Front helper only: `jq` via Alpine apk (not Python, not Node).
- Do not add Django/DRF/Angular build toolchains. Stub JS is hand-written.

## Project Structure Notes

Spine seed for this story:

```text
platform/
  TAIGA_PIN                         # unchanged
  back.Dockerfile                   # UPDATE
  front.Dockerfile                  # UPDATE
  docker-compose.override.yml       # leave unless forced
  entrypoint-back.sh                # CREATE (thin exec ok)
  patch-front-conf.sh               # CREATE → image 40_ hook
  addons.txt                        # CREATE
  README.md                         # UPDATE
addons/components/
  back/taiga_contrib_components/    # CREATE stub
  front/components.json             # CREATE stub
  front/components.js               # CREATE stub
tests/test_plugin_load.py           # CREATE
```

`.dockerignore` already excludes `docs/`, `tests/`, `_bmad/`. Do **not** add `addons` or `platform`.

### Previous story intelligence

Story **1.1** is `done` (`docs/implementation/1-1-overlay-scaffolding.md`). Learnings that bind 1.2:

- `platform/TAIGA_PIN` is the declared seed; Dockerfile `ARG` defaults and `${TAIGA_PIN:-…}` are copies enforced by tests. Do not invent a Makefile.
- ARG **must** be redeclared after `FROM` before `${TAIGA_PIN}` is referenced.
- `taiga-async` reuses `taiga-addons-back`, `pull_policy: never`, **no** override `entrypoint`.
- Build context is `${TAIGA_ADDONS_ROOT:?…}`; README must keep `.env` + `compose config` + `docker compose down` + “do not `docker compose pull`”.
- Live Docker was **absent**; 1.1 deferred AC-4 login to **1.3**. Same rule: skip live, do not fake.
- Deferred on purpose for this story: `test_override_does_not_replace_official_config_files` whole-file scan — **rework it here**.
- Do not claim compose-merge semantics with a fake in-test dict merge.

### Git intelligence

Recent commits:

- `ab0f10d` Mark story 1.1 done after review follow-ups (pin sync, `.env`, `pull_policy`, ARG redeclare, `requirements-dev.txt`, `.dockerignore`)
- `ed2d308` / `b591227` Story 1.1 initial (platform skeleton + tests + planning pack)

Repo is a git work tree on `master`, ahead of `origin/master` by 1. Baseline for this story file: `ab0f10d`. Working tree was clean at story creation.

Pattern: red tests first, then files, pytest as the proof. Do not mark live Docker tasks done unless Docker actually ran.

### Latest tech information

- Official app tag at planning: `taigaio/taiga-back:6.10.2` = `:latest` on Hub; `taiga-docker` `stable` `VERSION.md` may still say `6.9.0`. **Operator production tag wins; do not bump the pin in this story.**
- Official back image: Python 3.11 venv at `/opt/venv`, Django 3.x as shipped, `DJANGO_SETTINGS_MODULE=settings.config`.
- Official front image: `nginx:1.23-alpine` + bash; `docker-entrypoint.d` hooks; Slack zip inside the image is `6.10.1` (GitHub tags currently stop at `6.10.0`) — irrelevant; do not re-download Slack.
- Contrib contract (unchanged): `INSTALLED_APPS += ["taiga_contrib_<slug>"]` and `contribPlugins: ["plugins/<slug>/<slug>.json"]`. Pattern: https://github.com/taigaio/taiga-contrib-slack
- Official advanced volume of full `config.py` / `conf.json` still **ignores env** (docs.taiga.io setup-production “advanced configuration”). Forbidden as overlay default.

### References

- [Source: docs/planning/epics.md] Story 1.2, Epic 1, FR-3 / NFR-2
- [Source: docs/planning/prd.md] FR-3, NFR-2, UJ-1
- [Source: docs/planning/prd-addendum.md] Official extension points
- [Source: docs/planning/ARCHITECTURE-SPINE.md] AD-3, AD-4, AD-5, AD-9, structural seed
- [Source: docs/planning/architecture.md] How plugins actually load
- [Source: docs/implementation/1-1-overlay-scaffolding.md] Files, tests, review decisions
- [Source: docs/implementation/deferred-work.md] Override substring-scan rework
- [Source: tests/test_overlay_scaffolding.py] Regression fence
- Official: https://github.com/taigaio/taiga-back/tree/6.10.2/docker
- Official: https://github.com/taigaio/taiga-front/tree/6.10.2/docker
- Official: https://github.com/taigaio/taiga-docker/blob/stable/docker-compose.yml

### Project context reference

No `project-context.md`. Follow the spine and 1.1 review decisions.

## Dev Agent Record

### Agent Model Used

Grok 4.6 (bmad-dev-story)

### Implementation Plan

- Red: `tests/test_plugin_load.py` plus reworked 1.1 override/placeholder asserts. 12 failed, 19 passed, 3 skipped.
- Green: `addons.txt` + stub Django app + stub plugin; `settings.overlay` star-imports official `config` then appends; back Dockerfile COPY/ENV (official ENTRYPOINT left); front `40_` hook + `apk add jq`; README append-not-replace.
- Verify: `python -m pytest -q` → 31 passed, 3 skipped (no Docker, no jq). Live AC-3 inspect not executed.
- Review follow-up (2026-08-17): red tests for 13 [Patch] findings (12 failed). Green: AD-9 whole-tree COPY + `install-enabled-addons.sh` fan-out; overlay fail-closed; slug validation; front hook order-preserving dedup + in-place overwrite; `.gitattributes` LF; drop dead `entrypoint-back.sh` image COPY; tighten tests (no Python reimplementation of the front script). Full suite 37 passed, 3 skipped.

### Debug Log References

- RED: 12 failed, 19 passed, 3 skipped (`docker` / `jq` not on PATH)
- GREEN: 31 passed, 3 skipped (`test_docker_compose_config_merges_when_docker_present`, `test_front_patch_script_mutates_fixture_conf`, `test_live_overlay_images_load_stub_when_docker_present`)
- Full suite: `python -m pytest -q` → 31 passed, 3 skipped
- Live container inspect skipped honestly — Docker absent. Recorded in deferred-work for 1.3.
- Review follow-up RED: 12 failed, 25 passed, 3 skipped (findings not yet patched).
- Review follow-up GREEN: `python -m pytest -q` → 37 passed, 3 skipped (`test_docker_compose_config_merges_when_docker_present`, `test_front_patch_script_mutates_fixture_conf` no jq, `test_live_overlay_images_load_stub_when_docker_present`). Git `sh` used for install/patch script tests.

### Completion Notes List

- Append-not-replace: official `config.py` / `conf.json` are never copied or volume-mapped. Override YAML is still image-swap only.
- Back: `DJANGO_SETTINGS_MODULE=settings.overlay` baked into the image. Overlay does `from .config import *` then appends `taiga_contrib_<slug>` from `/opt/taiga-addons/addons.txt`. Official ENTRYPOINT left so `taiga-async` compose entrypoint is untouched; both processes share the same image/settings.
- `platform/entrypoint-back.sh` is a thin `exec` of official `/taiga-back/docker/entrypoint.sh` (spine). Not installed as image ENTRYPOINT.
- Front: `apk add jq`; official `30_` stays; `40_patch-front-conf.sh` appends `plugins/<slug>/<slug>.json` with order-preserving dedup (`reduce`/`index`, not `jq unique`) and in-place `cat` overwrite so `conf.json` keeps nginx mode/owner. Shipped-script run still `skipif` no `jq` — Python helper is not treated as proof of the script.
- Stub `taiga_contrib_components` is importable with `PYTHONPATH=addons/components/back`. Front module is `taigaContrib.components` (not `taigaComponents`).
- 1.1 `test_override_does_not_replace_official_config_files` now checks volumes, async entrypoint/command, and `environment`/`command`/`entrypoint` so a reset to `DJANGO_SETTINGS_MODULE=settings.config` cannot hide.
- AC-3 live inspect not executed — no Docker. Static tests only. Same honesty as 1.1 → 1.3.
- ✅ Resolved review finding [High]: `addons.txt` is the single enable switch — Dockerfiles `COPY addons` and `install-enabled-addons.sh` fans out enabled slugs at build.
- ✅ Resolved review finding [High]: `mktemp` no longer `mv`s a 0600 file over `conf.json`; contents are overwritten in place.
- ✅ Resolved review finding [High]: front hook no longer uses `jq unique` (sort); order-preserving dedup.
- ✅ Resolved review finding [High]: `.gitattributes` forces `*.sh text eol=lf`.
- ✅ Resolved review finding [High]: removed Python reimplementation as proof of `patch-front-conf.sh`.
- ✅ Resolved review finding [High]: overlay fails closed unless imported as the helper module `overlay`.
- ✅ Resolved review finding [Med]: override test inspects environment/command/entrypoint for `settings.config`.
- ✅ Resolved review finding [Med]: slugs validated (`^[a-z][a-z0-9_]*$`) in overlay + both shell scripts.
- ✅ Resolved review finding [Med]: vacuous `config.py` assertion removed.
- ✅ Resolved review finding [Med]: `entrypoint-back.sh` is no longer COPYed into the image (spine file kept in repo).
- ✅ Resolved review finding [Low]: stub AppConfig checked via AST + no `models.py`/`urls.py`.
- ✅ Resolved review finding [Low]: settings module cache restored after overlay import test.
- ✅ Resolved review finding [Low]: missing `addons.txt` raises `FileNotFoundError` with a diagnostic.

### File List

- platform/addons.txt
- platform/overlay.py
- platform/entrypoint-back.sh
- platform/install-enabled-addons.sh
- platform/patch-front-conf.sh
- platform/back.Dockerfile
- platform/front.Dockerfile
- platform/README.md
- .gitattributes
- addons/components/back/taiga_contrib_components/__init__.py
- addons/components/back/taiga_contrib_components/apps.py
- addons/components/front/components.json
- addons/components/front/components.js
- addons/components/back/.gitkeep (deleted)
- addons/components/front/.gitkeep (deleted)
- tests/test_plugin_load.py
- tests/test_overlay_scaffolding.py
- docs/implementation/1-2-plugin-load-without-replacing-official-config.md
- docs/implementation/sprint-status.yaml
- docs/implementation/deferred-work.md

### Change Log

- 2026-08-17: Implemented plugin load (addons.txt, settings.overlay, front 40_ hook, stub Addon). Status → review. Live Docker inspect deferred to 1.3.
- 2026-08-17: Addressed code review findings — 13 items resolved. Status → review.
- 2026-08-17: Marked done after review follow-ups.
