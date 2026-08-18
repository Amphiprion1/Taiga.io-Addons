---
baseline_commit: 2dacd0899b2ad6d10eb2672a8a3e90d9fe6f0064
---

# Story 1.3: Upgrade playbook and smoke test

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As an operator,
I want a written Upgrade playbook plus a smoke checklist,
so that bumping Official Taiga is a rehearsal, not an invention.

## Acceptance Criteria

1. **Given** `platform/UPGRADE.md` **When** I read it **Then** it lists: backup DB → pull official compose updates → bump pin → rebuild overlay → `up -d` → Addon migrate via official entrypoint → smoke catalog/picker/chips (or stub load until those exist) **And** it states core Taiga migrations are Official Taiga’s **And** it documents AD-5 fallback (front-from-source rebuild) as non-default.

2. **Given** a smoke script or documented curl/UI checks **When** I run them against a healthy overlay **Then** they fail if the stub Addon back app is missing from `INSTALLED_APPS` or the front plugin JSON is missing from `contribPlugins`.

## Tasks / Subtasks

- [x] Write `platform/UPGRADE.md` (AC: 1)
  - [x] Numbered operator sequence with the exact steps in AC-1 (backup → official compose pull → bump pin → rebuild → `up -d` → official entrypoint migrate → smoke)
  - [x] State that core Taiga migrations are Official Taiga’s (this repo never vendors or runs a substitute `migrate` for core)
  - [x] Document AD-5 fallback as **non-default**; default remains the runtime contrib plugin
  - [x] Until Epic 2/3 exist, smoke step = stub load (this story’s script). List catalog / picker / chips as later operator glances, not as automated checks yet
  - [x] Warn: one pin for **both** `taiga-back` and `taiga-front`; Hub `:latest` tags can diverge (see Latest tech)
  - [x] Pin-bump recipe must update `platform/TAIGA_PIN` **and** official `.env` `TAIGA_PIN`; Dockerfile ARG / override `${TAIGA_PIN:-…}` / `compose.env.example` are copies that tests fail if they drift
  - [x] Forbid `docker compose pull` of overlay images (`taiga-addons-back` / `taiga-addons-front` are local-only; `pull_policy: never`)
  - [x] Official `FROM` images are pulled by `docker compose build`, not by a blanket compose pull
- [x] Write fail-closed smoke (AC: 2)
  - [x] One implementation: `platform/smoke.py` (not a `.sh` plus a Python reimplementation)
  - [x] Reuse `platform/overlay.py` (`parse_addon_slugs`, `contrib_app_label`, `contrib_plugin_path`) — do not copy slug/path logic
  - [x] Fixture/offline mode so pytest can prove fail-closed **without** Docker
  - [x] Live mode: `docker compose exec` into `taiga-back` and `taiga-front` when a stack is up
  - [x] Exit non-zero if `taiga_contrib_components` ∉ `INSTALLED_APPS` **or** `plugins/components/components.json` ∉ `contribPlugins`
- [x] Operator docs + tests (AC: 1–2)
  - [x] Link `UPGRADE.md` + smoke command from `platform/README.md`; keep every 1.1 README needle
  - [x] Add `tests/test_upgrade_playbook.py` (playbook needles + smoke fixture fail/pass)
  - [x] If Docker **and** a running overlay stack exist: run live smoke. If either is absent: `skipif` honestly. Do **not** fake login or a live stack
- [x] Verify
  - [x] `python -m pytest -q` — 1.1 + 1.2 suites still green plus new tests
  - [x] Do not bump `platform/TAIGA_PIN`. Do not add models / REST / UI

### Review Findings

Code review 2026-08-17 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 1 decision (resolved → patch), 17 patches, 4 deferred, 8 dismissed.

- [x] [Review][Patch] **Rollback does not undo migrations — say so (decision: forward-fix only)** — Step 1 mandates a dump "until smoke passes", but Rollback only removes the override and cycles compose, and official core `migrate` has already run on boot (step 5) by the time smoke fails. Operator decision 2026-08-17: a bump is **one-way** once core migrate has run. The dump is **disaster recovery, not a routine rollback**. Rollback stays override-removal only; the playbook must state that limitation plainly instead of implying the dump is a rollback path. [platform/UPGRADE.md:10-21, :135-145]

- [x] [Review][Patch] Live smoke test is structurally unrunnable — probe and invocation both use `cwd=REPO`, which has no compose project, so it always skips and misreports the reason [tests/test_upgrade_playbook.py:32, :220]
- [x] [Review][Patch] `$TAIGA_ADDONS_ROOT` / `$POSTGRES_USER` are compose `.env` keys, empty in the operator's shell — both headline commands fail as written [platform/UPGRADE.md:17, :96, :106-108; platform/README.md:48]
- [x] [Review][Patch] `smoke.py` exits 0 on an empty slug list — a commented-out `addons.txt` turns the fail-closed gate green (verified: exit 0 with empty apps + empty conf) [platform/smoke.py:37-57, :167]
- [x] [Review][Patch] `test_upgrade_playbook_forbids_overlay_compose_pull` asserts presence, not prohibition — a playbook instructing a blanket pull passes all three asserts [tests/test_upgrade_playbook.py:98-102]
- [x] [Review][Patch] Known-broken seed pin not documented concretely — spec's own research says `taigaio/taiga-front:6.10.2` is a 404, so step 4 fails at the seed; playbook only hedges generically and omits the known shared tags [platform/UPGRADE.md:48-50]
- [x] [Review][Patch] Every live failure reports "no running overlay" — a crash-looping back, broken `settings.overlay`, or compose v1 all take the environment-absent branch; also shares exit code 1 with a real check failure [platform/smoke.py:104-133]
- [x] [Review][Patch] No `timeout=` on any `subprocess.run` — a hung daemon blocks the smoke and the suite indefinitely [platform/smoke.py:96-101; tests/test_upgrade_playbook.py:27-33, :216-221]
- [x] [Review][Patch] Playbook has no wait between `up -d` and smoke — running it mid-migrate yields a false "no running overlay" [platform/UPGRADE.md:64-71, :89-97]
- [x] [Review][Patch] Needle tests are whole-file substring scans (`"git" in lower`, OR-chains) with no ordering assertion — the anti-pattern deferred-work.md:9 records as resolved in 1.2 [tests/test_upgrade_playbook.py:69-80]
- [x] [Review][Patch] Playbook never re-runs the 1.1 merge verification (`docker compose -f … config`) after `git pull` — an upstream service rename silently invalidates the override [platform/UPGRADE.md:23-36]
- [x] [Review][Patch] `test_smoke_reuses_overlay_helpers_not_a_copy` is a source grep — a hand-rolled copy passes; `assert smoke.overlay is overlay` would be real [tests/test_upgrade_playbook.py:122-132]
- [x] [Review][Patch] `check_contrib_plugins` coerces a non-list `contribPlugins` to `[]` — a corrupted `conf.json` is misdiagnosed as a missing plugin [platform/smoke.py:47-51]
- [x] [Review][Patch] `pg_dump` line has no failure guard — the redirect creates the file even on failure, and `date +%Y%m%d` clobbers a same-day retry [platform/UPGRADE.md:15-18]
- [x] [Review][Patch] Volume snapshot offered as an equal backup alternative without stopping the DB — not crash-consistent [platform/UPGRADE.md:20-21]
- [x] [Review][Patch] No failure branch if `docker compose build` fails — playbook proceeds to `up -d` [platform/UPGRADE.md:64-71]
- [x] [Review][Patch] `deferred-work.md` converts unmet 1.1 AC-4 into permanent prose with no owning story [docs/implementation/deferred-work.md:11]
- [x] [Review][Patch] `README.md:30` "This story only ships the attach path" now contradicts the Upgrade section below it [platform/README.md:30]

- [x] [Review][Defer] Live code path has no test seam — `_run_live` JSON parsing and the flag XOR guard are unreachable without Docker [platform/smoke.py:104-174] — deferred, spec explicitly accepted skipif honesty
- [x] [Review][Defer] ASCII-apostrophe needle is brittle — `UPGRADE.md` mixes curly `’` (lines 4, 25, 57) with the ASCII `'` the test depends on [tests/test_upgrade_playbook.py:85] — deferred, pre-existing encoding mix
- [x] [Review][Defer] `git pull --ff-only` has no stated precondition or recovery for a dirty/diverged `taiga-docker` checkout [platform/UPGRADE.md:28-33] — deferred, operator-environment concern
- [x] [Review][Defer] Spec baseline says `tests/test_plugin_load.py` is "37 passed, 3 skipped"; it is 17 passed, 2 skipped both before and after this commit [docs/implementation/1-3-upgrade-playbook-and-smoke-test.md:190] — deferred, spec bookkeeping, nothing regressed

**Dismissed (8):** `TAIGA_ADDONS_TXT` not consulted by smoke (AD-9 prescribes the resolution order and forbids the host reading `/opt`); stale extra `taiga_contrib_*` apps not detected (spec scoped the checks to exactly two); relative `TAIGA_ADDONS_ROOT`; `--addons-file ""`; `OSError` after `shutil.which`; compose warnings prefixing JSON (compose writes those to stderr); rollback `rm`-before-`down` ordering (service names come from official `docker-compose.yml`); per-story framing in README headings.

## Dev Notes

This story **closes Epic 1**. It is documentation + a fail-closed smoke, not a pin bump and not Components domain.

**Completion honesty (same protocol as 1.1 / 1.2):** AC-2 “against a healthy overlay” is **not** satisfied by reading Dockerfiles. Fixture tests prove fail-closed. Live `docker compose exec` is optional (`skipif`). 1.1 AC-4 live **login** is an operator UI glance in `UPGRADE.md`, not an automated credentialed login.

### What you are building (and only that)

| Artifact | Role |
| --- | --- |
| `platform/UPGRADE.md` | Operator rehearsal for UJ-2 / FR-4 / NFR-1 |
| `platform/smoke.py` | Automated stub-load gate (AC-2) |
| `tests/test_upgrade_playbook.py` | Needles + fail-closed proof |
| `platform/README.md` | Pointer only |

### Required `UPGRADE.md` contents (needles tests will search)

The file must contain these **ideas as operator-visible text** (wording can vary; tests should match stable phrases below):

1. **Backup DB** first (Postgres volume / `pg_dump` via official `taiga-db`). Example shape:
   ```bash
   # from official taiga-docker/
   docker compose exec -T taiga-db pg_dump -U "$POSTGRES_USER" taiga > "taiga-backup-$(date +%Y%m%d).sql"
   ```
   User/db names come from official `.env` (`POSTGRES_USER`, typically `taiga`). Do not invent a second database.

2. **Pull official compose updates** = `git` update of the operator’s `taiga-docker` checkout on **`stable`**. Preserve `.env` and `docker-compose.override.yml`. **Do not** `git reset --hard` (official 6.6 migration doc uses that; it would wipe the override).

3. **Bump pin** = set the **same** explicit tag on:
   - `platform/TAIGA_PIN` (declared seed in this repo)
   - official `taiga-docker/.env` → `TAIGA_PIN=<tag>`
   - then run this repo’s pytest so ARG defaults / override `${TAIGA_PIN:-…}` / `compose.env.example` are updated if they drifted
   - **Never** `:latest`
   - **Before** bumping: both `taigaio/taiga-back:<tag>` **and** `taigaio/taiga-front:<tag>` must exist on Hub. Official `:latest` for back and front **diverge** (see Latest tech). One pin, two images.

4. **Rebuild overlay** = from official `taiga-docker/`:
   ```bash
   docker compose build
   docker compose up -d
   ```
   Not `docker compose pull` for `taiga-back` / `taiga-async` / `taiga-front` (local overlay tags). Build pulls official `FROM` images.

5. **Addon migrate via official entrypoint** — Official `/taiga-back/docker/entrypoint.sh` already runs `manage.py migrate` then `loaddata` then gunicorn. Overlay apps are in `INSTALLED_APPS` via `settings.overlay`, so Addon tables appear on boot **when they exist** (Epic 2). This repo does **not** add a second migrate command. `taiga-async` does **not** migrate (official async entrypoint is Celery only).

6. **Smoke**
   - Now: `python3 /absolute/path/to/Taiga.io-addons/platform/smoke.py` from `taiga-docker/` (compose project dir).
   - Later (Epic 3): login, Project settings catalog, User Story picker, kanban/backlog chips. List those as a **manual** glance section; do not pretend the APIs exist.

7. **Core migrations are Official Taiga’s** — a sentence tests can find, e.g. `core Taiga migrations are Official Taiga's`. Also state there is **no Taiga source merge** (NFR-1).

8. **AD-5 fallback is non-default**
   - Default: runtime contrib plugin already shipped (1.2).
   - Fallback (only if a later story cannot inject picker/chips into the pinned front tag): isolated front image built from the **matching official source tag** + a patch file **in this repo**. Not a vendor of `taiga-front`. Not the starting plan. If ever used, record it **in this same `UPGRADE.md`**.
   - Do not start that rebuild in this story.

Also document rollback (already in README): remove override, `docker compose down`, `docker compose up -d`. Addon tables (once Epic 2 exists) remain unused in Postgres (FR-5) — mention that; do not invent DROP scripts.

### Smoke implementation (do this, do not invent a second checker)

**File:** `platform/smoke.py`

**Reuse** (import from `overlay` with `sys.path` insert of `platform/`, same as `tests/test_plugin_load.py`):

- slugs ← `overlay.parse_addon_slugs(addons.txt)`
- expected app ← `overlay.contrib_app_label(slug)` → `taiga_contrib_components`
- expected plugin ← `overlay.contrib_plugin_path(slug)` → `plugins/components/components.json`

**Two modes, one code path for the assertions:**

```
check_installed_apps(apps: list[str], slugs) -> None   # raise SystemExit/SmokeError if missing
check_contrib_plugins(conf: dict, slugs) -> None       # same for contribPlugins
```

**Slug source (do not invent a second registry):**

Expected slugs come from **this repo’s** `platform/addons.txt`, resolved in order:

1. `--addons-file PATH`
2. `$TAIGA_ADDONS_ROOT/platform/addons.txt` (same env the override already requires)
3. `Path(__file__).resolve().parent / "addons.txt"` (works when invoked as `python3 /abs/.../platform/smoke.py`)

Never read `/opt/taiga-addons/addons.txt` on the **host**. That path exists only inside the image.

**Offline / tests** (no Docker):

```bash
python platform/smoke.py --apps-file apps.json --conf-file conf.json --addons-file platform/addons.txt
```

`--apps-file` is a JSON list of app labels. `--conf-file` is a front `conf.json` object. Missing either expected value → exit `1` + stderr that names the missing app **and/or** plugin path.

**Live** (default, no extra flags):

From official `taiga-docker/` (so compose finds the project). `UPGRADE.md` must show the absolute path (or `$TAIGA_ADDONS_ROOT/platform/smoke.py`).

1. Back — do **not** call `django.setup()` (official apps’ `ready()` may touch the DB). Import settings only:

   ```text
   docker compose exec -T taiga-back /opt/venv/bin/python -c
     "from django.conf import settings; import json; print(json.dumps(list(settings.INSTALLED_APPS)))"
   ```

   Image already has `DJANGO_SETTINGS_MODULE=settings.overlay`. `from django.conf import settings` loads `overlay` → star-imports official `config` (env) → appends addon apps. No DB required.

2. Front:

   ```text
   docker compose exec -T taiga-front cat /usr/share/nginx/html/conf.json
   ```

   Parse JSON; require each `plugins/<slug>/<slug>.json` in `contribPlugins`. Do **not** require `api` / `eventsUrl` / `baseHref` to change.

If `docker` / compose project is missing, live mode exits non-zero with a clear “no running overlay” message — tests `skipif` live; they do not treat that as a pass.

**Optional extra (not a substitute for AC-2):** assert plugin files exist at `/usr/share/nginx/html/plugins/components/{components.json,components.js}`. Nice; the **required** fail-closed checks are `INSTALLED_APPS` + `contribPlugins`.

**Do not:**

- Reimplement slug parsing
- Shell-out to `jq` (front container has `jq`; the smoke host may not)
- Use `curl` against `/api/v1/components/` (no REST until 2.2)
- Automate browser login
- `docker compose exec taiga-async` for this check (same image/settings; API container is enough)

### Files being modified — current state / change / preserve

| File | Today | This story changes | Must preserve |
| --- | --- | --- | --- |
| `platform/UPGRADE.md` | **does not exist** (spine seed name) | CREATE playbook | n/a |
| `platform/smoke.py` | **does not exist** | CREATE smoke | n/a |
| `tests/test_upgrade_playbook.py` | **does not exist** | CREATE | n/a |
| `platform/README.md` | Attach + append-not-replace + rollback | Add short “Upgrade” section linking `UPGRADE.md` and `python3 …/platform/smoke.py` | Every needle in `test_readme_documents_attach_and_pin` (see below) |
| `docs/implementation/deferred-work.md` | Live 1.1 login + 1.2 inspect deferred to 1.3 | After impl: note smoke artifact shipped; live still skipif if Docker/stack absent | Other deferred items (`TAIGA_PIN=latest` guard, bash-only README, unpinned `jq`) stay deferred |
| `platform/TAIGA_PIN` | `6.10.2` | **Do not change** | Declared seed |
| `platform/back.Dockerfile` | Overlay COPY + `settings.overlay` | **Do not change** | Pin ARG, no `:latest`, no `config.py` COPY, no `entrypoint-back.sh` COPY |
| `platform/front.Dockerfile` | `jq` + `40_` hook + fan-out | **Do not change** | Official `30_` stays |
| `platform/docker-compose.override.yml` | Image swap only | **Do not change** | No volumes of `config.py`/`conf.json`; async has no entrypoint/command; `pull_policy: never` |
| `platform/overlay.py` | Fail-closed append | **Import only** | Fail-closed + slug regex |
| `platform/addons.txt` | `components` | **Do not change** | |
| `platform/compose.env.example` | two keys | **Do not change** unless a test forces pin-copy sync — not this story | |
| `tests/test_overlay_scaffolding.py` | 20 passed, 1 skipped | **Do not break** | README needles, override invariants |
| `tests/test_plugin_load.py` | 17 passed, 2 skipped | **Do not break** | Live test still skipif; you may leave its docstring saying 1.3 owns smoke |
| Root `README.md` | Stale (“implementation not started”, next = 1.1) | **Out of scope** | Do not expand this story to rewrite marketing docs |

### README needles you will break if careless

`test_readme_documents_attach_and_pin` requires **all** of:

`TAIGA_ADDONS_ROOT`, `TAIGA_PIN`, `docker-compose.override.yml`, `docker compose`, current pin `6.10.2`, `.env`, `docker compose down`, `-f docker-compose.yml -f docker-compose.override.yml config`, `docker compose pull`

Add the UPGRADE/smoke pointer **without** removing those strings. Do not replace “do not `docker compose pull`” with a blanket pull instruction.

### Architecture compliance (must follow)

- **AD-1** No vendor/fork of `taiga-docker` / `taiga-back` / `taiga-front`. Playbook updates the operator’s official checkout; this repo stays overlay-only.
- **AD-2** One explicit pin. Seed stays `6.10.2`. Never `:latest`. Operator production tag wins **when they bump** — this story does not bump.
- **AD-3** Playbook must not tell the operator to volume-map a full `config.py` / `conf.json`.
- **AD-4** Back and async stay on the same overlay image. Migrate stays on the **API** official entrypoint only.
- **AD-5** Runtime plugin is default. Front-from-source rebuild is documented fallback, not implemented here.
- **AD-9** Smoke reads `addons.txt`; it does not hardcode a second registry.

### Out of scope (stop if you start these)

- Bumping `TAIGA_PIN` or aligning Hub tag mismatch (document it; do not “fix” by forking pins)
- Component models, migrations, REST (Epic 2)
- Catalog UI, picker, chips, AD-5 rebuild (Epic 3)
- Blocking `--build-arg TAIGA_PIN=latest` (already deferred)
- PowerShell README (already deferred; operators run `taiga-docker` on Linux)
- Pinning Alpine `jq` (already deferred)
- Kubernetes, extra compose services, custom gateway
- Changing `DJANGO_SETTINGS_MODULE`, async entrypoint, or official `.env` key names
- Installing `entrypoint-back.sh` as image `ENTRYPOINT` (1.2 review: dead trap)

### Testing requirements

Reuse `requirements-dev.txt` (`pytest`, `PyYAML`). No new runtime language.

**New tests (`tests/test_upgrade_playbook.py`)**

- `UPGRADE.md` exists and contains stable needles for: `backup` (or `pg_dump`), official compose update (`git` / `taiga-docker` / `stable`), bump pin / `TAIGA_PIN`, `docker compose build`, `up -d`, official entrypoint / `migrate`, `smoke`
- Explicit phrase that **core** migrations are Official Taiga’s
- Phrase that there is **no Taiga source merge** (NFR-1)
- AD-5 / front-from-source / fallback described as **non-default** / not the default
- Must **not** instruct `docker compose pull` of overlay images (assert the file still warns against overlay pull, same idea as README)
- `smoke.py` imports overlay helpers (source contains `parse_addon_slugs` / `contrib_app_label` / `contrib_plugin_path` usage — not a pasted regex copy)
- Fixture **fail**: apps list without `taiga_contrib_components` → exit ≠ 0
- Fixture **fail**: `conf.json` with `contribPlugins: []` or only Slack → exit ≠ 0
- Fixture **pass**: official-like apps + `taiga_contrib_components`, and `contribPlugins` including `plugins/components/components.json` (and maybe Slack first) → exit 0
- Both missing at once: still non-zero (do not stop after the first without reporting)
- Live test `skipif` no `docker` **or** compose exec fails to find `taiga-back` — do not start a full Taiga stack in CI

**1.1 / 1.2 tests you must keep green**

- README needle test
- Override no-config-replace / no-async-entrypoint
- Dockerfile pin / ARG / no `config.py` / no `conf.json` COPY
- Overlay fail-closed + stub import + front hook order
- Do **not** turn 1.2’s `test_live_overlay_images_load_stub_when_docker_present` into a required pass; it builds images (slow, needs Hub pull). 1.3 live smoke assumes an **already running** overlay.

**Honesty**

Do not mark live subtasks `[x]` unless `docker compose exec` actually ran. Fixture tests are enough to mark AC-2’s fail-closed behavior done.

### Library / framework

- No new app runtime. Official Django / nginx stay as shipped.
- Smoke is stdlib + existing `overlay.py`. Do not add requests, docker-py, Playwright, or jq-on-the-host.
- Do not add Django/DRF/Angular toolchains.

## Project Structure Notes

Spine seed after this story:

```text
platform/
  TAIGA_PIN                         # unchanged
  UPGRADE.md                        # CREATE
  smoke.py                          # CREATE
  README.md                         # UPDATE (link only)
  back.Dockerfile                   # unchanged
  front.Dockerfile                  # unchanged
  docker-compose.override.yml       # unchanged
  overlay.py                        # import only
  addons.txt                        # unchanged
  patch-front-conf.sh               # unchanged
  install-enabled-addons.sh         # unchanged
  entrypoint-back.sh                # unchanged (repo spine; not image ENTRYPOINT)
tests/test_upgrade_playbook.py      # CREATE
```

No UX spec. No `project-context.md`. Follow the spine.

### Previous story intelligence

**1.1** (`docs/implementation/1-1-overlay-scaffolding.md`, `done`):

- `platform/TAIGA_PIN` is the declared seed; Dockerfile ARG defaults and `${TAIGA_PIN:-…}` are copies enforced by tests. No Makefile.
- ARG must be redeclared after `FROM`.
- `taiga-async` reuses `taiga-addons-back`, `pull_policy: never`, **no** override entrypoint.
- Build context is `${TAIGA_ADDONS_ROOT:?…}`. README `.env` is required (one-shot `export` is not enough).
- Live Docker was **absent**; AC-4 login deferred **here**. Close it as a **documented operator glance**, not a fake login.
- Do not claim compose-merge semantics with a fake in-test dict merge.

**1.2** (`docs/implementation/1-2-plugin-load-without-replacing-official-config.md`, `done`):

- Append-not-replace: `settings.overlay` + front `40_` hook. Official `config.py` / `conf.json` never copied or volume-mapped.
- `addons.txt` is the single enable switch; Dockerfiles `COPY addons/` and `install-enabled-addons.sh` fans out.
- Overlay fails closed unless imported as helper `overlay` or as `settings.overlay` next to official `config`.
- Front hook: order-preserving dedup (`reduce`/`index`, **not** `jq unique`); in-place `cat` overwrite (do not `mv` a 0600 tmp over `conf.json`).
- `.gitattributes` forces `*.sh` LF. If you add a `.sh`, it must stay LF. Prefer `smoke.py` so this does not apply.
- `entrypoint-back.sh` is a thin `exec` of official entrypoint — **not** installed in the image.
- **Do not** prove a shell script with a Python reimplementation (1.2 review finding). That is why smoke is Python with fixture tests calling the **same** functions.
- Slugs: `^[a-z][a-z0-9_]*$`.
- Live AC-3 inspect skipped — Docker absent. 1.3 smoke is the artifact; live still skipif.
- Stub module name is `taigaContrib.components` — **never** `taigaComponents`.

**Deferred-work that is NOT yours to fix**

- `TAIGA_PIN=latest` build-arg guard
- PowerShell README
- Unpinned `apk add jq`

**Deferred-work that IS yours**

- Ship the playbook + smoke so 1.1 AC-4 and 1.2 AC-3 have an operator path. If Docker is still absent, leave live unchecked and say so in Debug Log.

### Git intelligence

HEAD `2dacd08` — *Mark story 1.2 done after review follow-ups.*

Recent pattern: red tests first, then files, pytest as proof. Review follow-ups added fail-closed / AD-9 fan-out / LF shebangs. Do not regress those.

Repo is `master`, ahead of `origin/master`. Working tree at story creation should stay limited to this story’s files.

### Latest tech information

Verified 2026-08-17 against Docker Hub API:

| Image | `:latest` digest alias | Highest explicit tag | Same tag on the other image? |
| --- | --- | --- | --- |
| `taigaio/taiga-back` | **6.10.2** (pushed 2026-07-02) | 6.10.2 | **`taiga-front:6.10.2` = 404** |
| `taigaio/taiga-front` | **6.10.3** (pushed 2026-05-18) | 6.10.3 | **`taiga-back:6.10.3` = 404** |

Shared tags that **do** exist on both include `6.9.0`, `6.8.2`, `6.8.1`, `6.7.1`, `6.7.0`, `6.6.0`.

**Playbook implication:** official Hub `:latest` is **not** a pair. The overlay pin is one tag for both `FROM` lines (AD-2). Before an operator bump, they must confirm **both** tags exist. This story does **not** change the seed `6.10.2` (AD-2: explicit commit when the operator chooses). Building `FROM taigaio/taiga-front:6.10.2` will fail today — document that as a pin-selection constraint, do not silently split pins.

Official upgrade docs:

- `taiga-docker` production branch is **`stable`** (not `main`).
- https://docs.taiga.io/upgrades-docker-migrate.html is the **6.6 `.env` migration**, not a routine pin bump. Do not copy its `git reset --hard origin/main`.
- Routine official motion: update the `taiga-docker` git checkout, keep `.env`, `docker compose up -d`. Overlay inserts **build overlay images from the new pin** in the middle.
- Official back 6.10.2 entrypoint still: `migrate` → `loaddata initial_project_templates` → gunicorn. Addon migrate is that same `migrate`.
- Official advanced volume of full `config.py` / `conf.json` still **ignores env**. Forbidden as overlay default (AD-3).
- Compose file format remains `3.5` compatible. `docker compose` v2 (not `docker-compose`).

### References

- [Source: docs/planning/epics.md] Story 1.3, Epic 1, FR-4, NFR-1
- [Source: docs/planning/prd.md] FR-4, NFR-1, UJ-2, SM-1, Glossary “Upgrade playbook”
- [Source: docs/planning/prd-addendum.md] Official extension points; Hub vs `taiga-docker` VERSION.md mismatch
- [Source: docs/planning/ARCHITECTURE-SPINE.md] AD-1–AD-5, AD-9, structural seed `platform/UPGRADE.md`
- [Source: docs/planning/architecture.md] Upgrade playbook (operator) § steps 1–7
- [Source: docs/implementation/1-1-overlay-scaffolding.md] Pin copies, `pull_policy`, AC-4 deferral
- [Source: docs/implementation/1-2-plugin-load-without-replacing-official-config.md] Overlay settings, front hook, live-inspect deferral
- [Source: docs/implementation/deferred-work.md] What 1.3 owns vs what stays deferred
- [Source: tests/test_overlay_scaffolding.py] README needle fence
- [Source: tests/test_plugin_load.py] Overlay import helper + skipif honesty
- Official: https://github.com/taigaio/taiga-docker (`stable`)
- Official: https://docs.taiga.io/upgrades-docker-migrate.html (do not cargo-cult)
- Official: https://github.com/taigaio/taiga-back/blob/6.10.2/docker/entrypoint.sh

### Project context reference

No `project-context.md`. Follow the spine and 1.1 / 1.2 review decisions.

## Dev Agent Record

### Agent Model Used

Grok 4.6 (bmad-dev-story)

### Implementation Plan

- Red: `tests/test_upgrade_playbook.py` against missing `UPGRADE.md` / `smoke.py` / README pointer. 13 failed, 1 skipped.
- Green: `platform/UPGRADE.md` operator sequence; `platform/smoke.py` reuses `overlay` helpers; fixture mode for pytest; live `docker compose exec` path; README Upgrade section; deferred-work notes that smoke shipped.
- Verify: `python -m pytest -q` → 50 passed, 4 skipped. Pin left at `6.10.2`. No models / REST / UI.
- Post-review (2026-08-17): red tests for 18 [Patch] findings (15 failed); green playbook honesty + smoke fail-closed/env-vs-exec + compose-dir; full suite 64 passed, 4 skipped.

### Debug Log References

- RED: 13 failed, 1 skipped (`test_live_smoke_when_overlay_stack_running` — Docker not on PATH)
- GREEN: playbook needle wrap (`Official\nTaiga's`) failed once; put `core Taiga migrations are Official Taiga's` on one line
- Full suite: `python -m pytest -q` → 50 passed, 4 skipped (`test_docker_compose_config_merges_when_docker_present`, `test_front_patch_script_mutates_fixture_conf`, `test_live_overlay_images_load_stub_when_docker_present`, `test_live_smoke_when_overlay_stack_running`)
- Live `docker compose exec` was **not** executed — Docker absent. Fixture tests prove fail-closed. skipif is honest.
- POST-REVIEW RED: 15 failed, 12 passed, 1 skipped (new playbook/smoke assertions against unpatched artifacts)
- POST-REVIEW GREEN: `python -m pytest -q` → 64 passed, 4 skipped (same four live/Docker skips; no new skip class)

### Completion Notes List

- `platform/UPGRADE.md` is the UJ-2 / FR-4 rehearsal: backup (`pg_dump`) → official `taiga-docker` `stable` git update (no `reset --hard`) → one pin on `platform/TAIGA_PIN` and official `.env` → `docker compose build` + `up -d` → official entrypoint migrate → `smoke.py`.
- Playbook states **core Taiga migrations are Official Taiga's** and **no Taiga source merge**. AD-5 front-from-source rebuild is documented as **non-default**. Overlay `docker compose pull` is forbidden; official `FROM` images come in via `build`.
- Catalog / picker / chips / login are later operator glances, not automated checks. 1.1 AC-4 login is that glance.
- `platform/smoke.py` is the only checker. Slugs come from `overlay.parse_addon_slugs`; expected app/plugin from `contrib_app_label` / `contrib_plugin_path`. Offline `--apps-file` / `--conf-file`; live default execs `taiga-back` + `taiga-front`. Both missing items are reported in one non-zero exit. Host never reads `/opt/taiga-addons/addons.txt`.
- `platform/README.md` Upgrade section links `UPGRADE.md` and `python3 "$TAIGA_ADDONS_ROOT/platform/smoke.py"`. 1.1 README needles kept.
- `platform/TAIGA_PIN` unchanged (`6.10.2`). No overlay / Dockerfile / compose / Addon domain changes.
- Live smoke skipif — Docker absent. Recorded in deferred-work; fixture tests satisfy AC-2 fail-closed.
- ✅ Resolved review finding [Patch]: rollback states dump is disaster recovery; bump is one-way once core migrate has run
- ✅ Resolved review finding [Patch]: live probe uses `$TAIGA_DOCKER` / `--compose-dir`, not this repo as a compose project
- ✅ Resolved review finding [Patch]: playbook/README source official `.env`; `pg_dump` expands `POSTGRES_USER` inside the db container
- ✅ Resolved review finding [Patch]: empty `addons.txt` is fail-closed (exit 1)
- ✅ Resolved review finding [Patch]: overlay `docker compose pull` asserted as prohibition, not mere presence
- ✅ Resolved review finding [Patch]: seed `taiga-front:6.10.2` documented as Hub 404; shared tags listed
- ✅ Resolved review finding [Patch]: live env missing = exit 2 "no running overlay"; unhealthy exec = exit 3 "overlay exec failed"; check fail = exit 1
- ✅ Resolved review finding [Patch]: every `subprocess.run` (smoke + live probe) has `timeout=`
- ✅ Resolved review finding [Patch]: rebuild uses `up -d --wait`; do not smoke mid-migrate
- ✅ Resolved review finding [Patch]: operator sequence needles asserted in order
- ✅ Resolved review finding [Patch]: step 2 re-runs `docker compose -f … config` after `git pull`
- ✅ Resolved review finding [Patch]: `assert smoke.overlay is overlay` (not a source grep)
- ✅ Resolved review finding [Patch]: non-list `contribPlugins` is "corrupted conf.json", not a missing plugin
- ✅ Resolved review finding [Patch]: `pg_dump` second-precision stamp + `rm -f` on failure
- ✅ Resolved review finding [Patch]: volume snapshot is not crash-consistent unless DB is stopped
- ✅ Resolved review finding [Patch]: `docker compose build || exit 1` — do not `up -d` after a failed build
- ✅ Resolved review finding [Patch]: 1.1 AC-4 automated login owned by `3-1-project-settings-catalog-ui`
- ✅ Resolved review finding [Patch]: README no longer claims "this story only ships the attach path"

### File List

- platform/UPGRADE.md
- platform/smoke.py
- platform/README.md
- tests/test_upgrade_playbook.py
- docs/implementation/deferred-work.md
- docs/implementation/1-3-upgrade-playbook-and-smoke-test.md
- docs/implementation/sprint-status.yaml

### Change Log

- 2026-08-17: Implemented upgrade playbook + fail-closed stub-load smoke. Status → review. Live Docker exec skipif (Docker absent).
- 2026-08-17: Addressed code review findings - 18 items resolved (Date: 2026-08-17)
- 2026-08-17: Marked done after review follow-ups.
