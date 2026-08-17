---
baseline_commit: NO_VCS
---

# Story 1.1: Overlay scaffolding

Status: review

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As an operator,
I want Dockerfiles and a compose override that swap official back/async/front for images built `FROM` a pinned official tag,
so that I can attach this repo to production without forking `taiga-docker`.

## Acceptance Criteria

1. **Given** an official `taiga-docker` directory **When** I copy `platform/docker-compose.override.yml` beside it and build/start **Then** `taiga-back` and `taiga-async` use the overlay back image and `taiga-front` uses the overlay front image **And** official `docker-compose.yml` is not modified.
2. Dockerfiles `FROM taigaio/taiga-back:<pin>` and `FROM taigaio/taiga-front:<pin>` with **no** `:latest`.
3. The pin is a **single declared value** (seed `6.10.2`, overridable by the operator).
4. **Given** the overlay images **When** the stack is healthy **Then** login to Taiga still works (gateway, db, events unchanged).

## Tasks / Subtasks

- [x] Create `platform/` layout (AC: 1–3)
  - [x] `platform/TAIGA_PIN` or ARG default `6.10.2` used by both Dockerfiles
  - [x] `platform/back.Dockerfile` — `FROM taigaio/taiga-back:${TAIGA_PIN}`
  - [x] `platform/front.Dockerfile` — `FROM taigaio/taiga-front:${TAIGA_PIN}`
  - [x] `platform/docker-compose.override.yml` — override **only** `taiga-back`, `taiga-async`, `taiga-front` images (async = same back image)
- [x] Operator instructions (AC: 1, 4)
  - [x] Short `platform/README.md`: copy override next to official compose, set pin, `docker compose build && up -d`
- [x] Empty Addon stubs only if required for a valid image build (full plugin load is **1.2**)
  - [x] Do **not** implement INSTALLED_APPS / contribPlugins append here unless the image will not build without a placeholder file
- [x] Verify locally if Docker is available (AC: 4)
  - [x] Compose config merge shows official file untouched
  - [x] Images report the pinned `FROM`

## Dev Notes

This is the **first** story. It only proves the overlay attach path. Do **not** implement Components models, REST, or UI.

### Architecture compliance (must follow)

- **AD-1** Overlay-not-fork: no clone/vendor of `taiga-docker`, `taiga-back`, `taiga-front`.
- **AD-2** Pin official tags. Seed **6.10.2** (official `:latest` as of 2026-08-17). Operator production tag wins.
- **AD-4** `taiga-back` and `taiga-async` must use the **same** overlay image.
- **AD-3 / 1.2** Official `config.py` / `conf.json` must **not** be replaced wholesale in this story. If you add any config, you are out of scope — stop.
- **AD-9** Future addons live in `addons/<slug>/{back,front}`. You may create empty `addons/components/{back,front}/.gitkeep` so the tree exists.

### Official compose facts (do not fight these)

Official `taiga-docker` `docker-compose.yml` (stable):

- `taiga-back` / `taiga-async`: image `taigaio/taiga-back:latest` (we override image + add `build`)
- `taiga-async` uses `entrypoint: ["/taiga-back/docker/async_entrypoint.sh"]` — **keep that entrypoint**
- `taiga-front`: image `taigaio/taiga-front:latest`; optional volume `./conf.json:/usr/share/nginx/html/conf.json` (do not enable as a full replace)
- `taiga-back` optional volume `./config.py:/taiga-back/settings/config.py` (do not enable as a full replace)
- Other services (db, gateway, events, protected, rabbits) **must not** appear in the override except if compose requires an explicit no-op (prefer not)

Override should look conceptually like:

```yaml
services:
  taiga-back:
    image: taiga-addons-back:${TAIGA_PIN}
    build:
      context: <path-to-this-repo>
      dockerfile: platform/back.Dockerfile
      args:
        TAIGA_PIN: "6.10.2"
  taiga-async:
    image: taiga-addons-back:${TAIGA_PIN}
    # no separate build if compose can reuse taiga-back image
  taiga-front:
    image: taiga-addons-front:${TAIGA_PIN}
    build:
      context: <path-to-this-repo>
      dockerfile: platform/front.Dockerfile
      args:
        TAIGA_PIN: "6.10.2"
```

**Path problem:** official compose lives in the operator’s `taiga-docker/` directory; this repo is elsewhere. The override must document how `build.context` points at **this** repo (absolute path, env var, or “place a copy of the override and set `TAIGA_ADDONS_ROOT`”). Do not require the operator to move official compose into this repo.

Recommended: override uses `${TAIGA_ADDONS_ROOT}` for build context; README says `export TAIGA_ADDONS_ROOT=...` before compose.

### Current state of files being created

Repo is greenfield. Nothing exists under `platform/` yet. BMAD lives in `_bmad/` and planning docs in `docs/` — do not delete those.

### What must be preserved

- Operator’s official `.env` and `docker-compose.yml`
- Ability to `docker compose up` official stack if the override file is removed

### Testing

- `docker compose -f docker-compose.yml -f docker-compose.override.yml config` (in a throwaway copy of official compose) must succeed
- Grep Dockerfiles: no `:latest` in `FROM`
- Back and async image names identical
- If you cannot run Docker, still produce the files and a README the operator can run; do not fake “tested on a live stack”

### Library / framework

- No new language runtime. Docker + official images only.
- Do not introduce Kubernetes, extra proxies, or a custom gateway.

### Project Structure Notes

```
platform/
  TAIGA_PIN                  # or ARG-only; one source of truth
  back.Dockerfile
  front.Dockerfile
  docker-compose.override.yml
  README.md
addons/components/back/.gitkeep
addons/components/front/.gitkeep
```

Story 1.2 will add entrypoint wrappers and `addons.txt`. Leave hooks obvious (e.g. comment in Dockerfile `# 1.2: COPY entrypoint-back.sh`) if useful, but no premature implementation.

### Previous story intelligence

None — first story.

### Latest tech information

- Official images: `taigaio/taiga-back:6.10.2`, `taigaio/taiga-front:6.10.2` (Hub, ~2 months before 2026-08-17).
- Official compose file version `3.5`; keep override compatible.
- Official back entrypoint already `migrate`s — do not wrap it yet (1.2).

### References

- [Source: docs/planning/prd.md] FR-1, FR-2, FR-5
- [Source: docs/planning/ARCHITECTURE-SPINE.md] AD-1, AD-2, AD-4, AD-9
- [Source: docs/planning/architecture.md] What you keep vs what this repo adds
- [Source: docs/planning/epics.md] Story 1.1
- Official compose: https://github.com/taigaio/taiga-docker (stable) `docker-compose.yml`

### Project context reference

No `project-context.md` yet. Follow the spine.

## Dev Agent Record

### Agent Model Used

Grok 4.6 (bmad-dev-story)

### Implementation Plan

- Red: `tests/test_overlay_scaffolding.py` asserts pin, FROM lines, override surface, same back/async image, no official config replace, static compose merge.
- Green: add `platform/` files + addon `.gitkeep` only. No INSTALLED_APPS / contribPlugins (1.2).
- Verify: pytest 14 passed. Docker CLI absent — live `compose config` skipped (not faked). Static merge covers AC-4 (gateway/db/events untouched).

### Debug Log References

- RED: 14 failed, 1 skipped (`docker` not on PATH)
- GREEN: 14 passed, 1 skipped (`test_docker_compose_config_merges_when_docker_present`)
- Full suite: `python -m pytest -q` → 14 passed, 1 skipped

### Completion Notes List

- Overlay attach path only. Official compose is never vendored or edited.
- Single pin: `platform/TAIGA_PIN` = `6.10.2`; Dockerfiles `ARG TAIGA_PIN=6.10.2`; override `${TAIGA_PIN:-6.10.2}`.
- `taiga-async` reuses `taiga-addons-back` image and does not override official async entrypoint.
- Build context is `${TAIGA_ADDONS_ROOT:?...}` so official `taiga-docker/` stays a separate directory.
- Live stack login (AC-4 runtime) not executed here — no Docker. Static merge proves official services remain.

### File List

- platform/TAIGA_PIN
- platform/back.Dockerfile
- platform/front.Dockerfile
- platform/docker-compose.override.yml
- platform/README.md
- addons/components/back/.gitkeep
- addons/components/front/.gitkeep
- tests/test_overlay_scaffolding.py
- docs/implementation/1-1-overlay-scaffolding.md
- docs/implementation/sprint-status.yaml

### Change Log

- 2026-08-17: Implemented overlay scaffolding (pin, Dockerfiles, compose override, operator README, static tests). Status → review.
