# Addendum — Taiga Addons (not PRD)

Mechanism, rejected alternatives, and version notes. Architecture owns the binding decisions.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Taiga **custom attributes** | Per-story fields; no reusable Project catalog + 0–N Assignment + Chips. |
| Taiga **tags** | Freeform, not a controlled catalog, not Project-admin curated in the Jira-component sense. |
| Fork `taiga-back` / `taiga-front` | Upgrade is a merge. Violates the Overlay kit job. |
| Vendor official `taiga-docker` into this repo | Operator already has production compose; forking it doubles upgrade surface. |
| Sidecar microservice + iframe | Different auth/session, worse UX, still need front hooks for Chips. |

## Official extension points (as of Taiga 6 contrib plugins)

- **Back:** Python package, `INSTALLED_APPS += ["taiga_contrib_*"]`, own Django migrations, own REST. Pattern: `taiga-contrib-slack` and sibling `taigaio/taiga-contrib-*` repos.
- **Front:** compiled assets under `dist/plugins/<name>/`, registered in `dist/conf.json` → `contribPlugins: ["plugins/<name>/<name>.json"]`.
- **Docker official:** `taigaio/taiga-docker` (use `stable` for production). App images: `taigaio/taiga-back`, `taigaio/taiga-front`. Current published app tag at authoring: **6.10.2** (also `:latest`). `taiga-docker` `stable` `VERSION.md` still listed **6.9.0** when checked — operator production tag is authoritative; overlay `FROM` that tag.
- **Advanced Docker config:** official compose can volume-map `config.py` (back) and `conf.json` (front). Overlay may bake those into custom images or map snippets — architecture chooses.

## Front hook risk

Community guidance: some contrib plugins only add pages (Slack). Injecting into **user-story detail** and **kanban/backlog cards** may require the front instance to “know” the plugin (compile-modules, as `taiga-contrib-subscriptions` historically did). That is a rebuild of front-from-source, not a patch of a running `dist/`. Architecture must pick the lowest-friction hook that still satisfies FR-14 and FR-15.

## Suggested repo seed (architecture will ratify)

```
addons/components/{back,front}/
platform/{docker-compose.override.yml,back.Dockerfile,front.Dockerfile,snippets/,UPGRADE.md}
docs/planning/   docs/implementation/
```

## Versions noted 2026-08-17

- Official `taigaio/taiga-back:6.10.2` = `:latest`
- Official `taiga-docker` stable `VERSION.md` = `6.9.0`
- Taiga 6 front is AngularJS 1.x; back is Django + DRF
