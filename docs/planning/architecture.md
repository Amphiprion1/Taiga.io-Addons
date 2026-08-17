# Architecture — Taiga Addons overlay kit

Human reading of the spine in `architecture/architecture-Taiga.io-addons-2026-08-17/ARCHITECTURE-SPINE.md`. Decisions are the `AD-n` rules; this page explains how they fit a running official Docker stack.

## What you keep vs what this repo adds

You already run official `taiga-docker`. That checkout stays yours. This repo never copies `docker-compose.yml`.

You drop **one** file next to it: `docker-compose.override.yml`. That file only changes three services:

| Service | Change |
| --- | --- |
| `taiga-back` | image → overlay back (same pin as official) |
| `taiga-async` | **same** overlay back image (AD-4) |
| `taiga-front` | image → overlay front |

Gateway, Postgres, RabbitMQ, events, protected stay official.

## Why not a fork

Official Taiga upgrades by pulling new images. A fork upgrades by merging. The overlay exists so an upgrade is: **change the pin → rebuild two images → boot (Addon migrations run with official `migrate`) → smoke-test plugins**.

Current official app tag at authoring (2026-08-17): **`6.10.2`**. `taiga-docker` `stable` `VERSION.md` still listed `6.9.0`. **Your production tag is the pin.** Never `:latest`.

## How plugins actually load

Official pattern (`taiga-contrib-slack` and siblings):

1. **Back:** `pip install` a Django app, then `INSTALLED_APPS += ["taiga_contrib_<slug>"]`. Official `entrypoint.sh` already runs `manage.py migrate`, so Addon tables appear on boot.
2. **Front:** copy compiled plugin to `dist/plugins/<slug>/` and add `"plugins/<slug>/<slug>.json"` to `conf.json` → `contribPlugins`. Official front in Docker serves from `/usr/share/nginx/html/` and can map `conf.json`.

Official “advanced” volume of a **full** `config.py` / `conf.json` **ignores env vars**. The overlay must not do that by default (AD-3). Entrypoint wrappers **append** after official generation.

## Components data

Two Addon tables only:

- `Component` — `project_id` (FK to Official Taiga Project), `name`, `order`
- `Assignment` — `(userstory_id, component_id)` unique

No columns on Official Taiga `userstories_userstory`. Delete Component → delete Assignment rows; User Stories stay.

Permissions (AD-7):

- Catalog write: Project admin
- Assignment write: User Story modify
- Everything else readable to Project viewers (needed for picker and Chips)

REST is Addon-owned under `/api/v1/components/...`, JWT is Official Taiga’s.

## Front: picker and Chips

Slack-style plugins are often **admin pages**. Chips need injection into **kanban/backlog cards** and the **User Story detail**. Community note: some plugins require the front build to know they exist.

**Default (AD-5):** a runtime contrib plugin that injects into known DOM after AngularJS view load. Lowest upgrade tax.

**Fallback:** rebuild front from the **same git tag as the pin**, apply a patch stored in this repo. That is the upgrade tax and must be called out in `UPGRADE.md` if used. It is not the starting plan.

## Upgrade playbook (operator)

1. Note current pin and back up Postgres (you already should before any Taiga upgrade).
2. Pull official `taiga-docker` updates as you normally would.
3. Set this repo’s pin to the new official back/front tag.
4. `docker compose build` the overlay images (from this repo or via override `build:`).
5. `docker compose up -d` in the official directory. Official entrypoint migrates core **and** Addon apps.
6. Smoke: login, open Project settings (catalog), open a User Story (picker), glance kanban (Chips).
7. If a front hook broke, see AD-5 fallback — do not start editing official `taiga-front` in place.

## Next Addon

Add `addons/<slug>/{back,front}`, register the slug in `platform/addons.txt`. Do not invent a second compose override or a second permission system.
