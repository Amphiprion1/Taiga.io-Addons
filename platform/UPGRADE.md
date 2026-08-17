# Upgrade playbook

Rehearse an Official Taiga bump. There is **no Taiga source merge** in this repo
(NFR-1). You update the operator’s official `taiga-docker` checkout and rebuild
two overlay images from one explicit pin. **core Taiga migrations are Official Taiga's** — this overlay never vendors or runs a substitute `migrate` for core.

Do not volume-map a full `config.py` or `conf.json`. Append-not-replace stays
in force (AD-3).

## 1. Backup the database

Do this first. User and database names come from official `.env`
(`POSTGRES_USER`, typically `taiga`). Do not invent a second database.

```bash
# from official taiga-docker/
docker compose exec -T taiga-db pg_dump -U "$POSTGRES_USER" taiga > "taiga-backup-$(date +%Y%m%d).sql"
```

A Postgres volume snapshot is also acceptable. Keep the dump until smoke
passes.

## 2. Pull official compose updates

Update the operator’s official `taiga-docker` git checkout on the **`stable`**
branch (not `main`). Preserve `.env` and `docker-compose.override.yml`.

```bash
cd /path/to/taiga-docker
git fetch origin
git checkout stable
git pull --ff-only origin stable
```

**Do not** `git reset --hard`. Official 6.6 migration docs use that; it would
wipe the overlay override and your `.env`.

## 3. Bump the pin

One pin for **both** `taiga-back` and `taiga-front`. Hub `:latest` tags can
diverge (back `:latest` and front `:latest` are not a pair). Never `:latest`.

Before bumping, confirm **both** Hub tags exist:

- `taigaio/taiga-back:<tag>`
- `taigaio/taiga-front:<tag>`

If either 404s, pick a shared tag that exists on both (do not split pins).
The seed in this repo is `6.10.2`; that is a declared pin, not a promise that
both Hub tags always exist.

Set the **same** explicit tag on:

1. `platform/TAIGA_PIN` (declared seed in this repo)
2. official `taiga-docker/.env` → `TAIGA_PIN=<tag>`

Then run this repo’s pytest. Dockerfile `ARG` defaults, override
`${TAIGA_PIN:-…}`, and `compose.env.example` are **copies** of
`platform/TAIGA_PIN` — tests fail if they drift. Update those copies if
pytest says they drifted.

This story does not bump the seed. When *you* bump, it is an explicit commit.

## 4. Rebuild the overlay

From official `taiga-docker/` (compose project directory):

```bash
docker compose build
docker compose up -d
```

**Do not** `docker compose pull` overlay images. `taiga-addons-back` and
`taiga-addons-front` are local-only (`pull_policy: never`). `taiga-async`
reuses the back overlay image. Official `FROM` images
(`taigaio/taiga-back:<pin>`, `taigaio/taiga-front:<pin>`) are pulled by
`docker compose build`, not by a blanket compose pull.

## 5. Addon migrate via official entrypoint

Official `/taiga-back/docker/entrypoint.sh` already runs `manage.py migrate`,
then `loaddata`, then gunicorn. Overlay apps are in `INSTALLED_APPS` via
`settings.overlay`, so Addon tables appear on boot **when they exist**
(Epic 2). This repo does **not** add a second migrate command.

`taiga-async` does **not** migrate (official async entrypoint is Celery only).
Migrate stays on the API container.

## 6. Smoke

### Automated stub load (now)

From official `taiga-docker/` so compose finds the project:

```bash
python3 "$TAIGA_ADDONS_ROOT/platform/smoke.py"
```

(`TAIGA_ADDONS_ROOT` is already required in official `.env`.) Fail-closed:
exit non-zero if `taiga_contrib_components` is missing from `INSTALLED_APPS`
or `plugins/components/components.json` is missing from `contribPlugins`.

Offline / fixture (no Docker):

```bash
python3 "$TAIGA_ADDONS_ROOT/platform/smoke.py" \
  --apps-file apps.json --conf-file conf.json \
  --addons-file "$TAIGA_ADDONS_ROOT/platform/addons.txt"
```

### Later operator glances (Epic 3 — not automated yet)

When catalog / picker / chips exist, glance these after stub smoke. They are
**not** automated checks in this playbook:

- Login still works (operator UI glance; not a credentialed script)
- Project settings → Components catalog
- User Story detail → picker
- Kanban / backlog → chips

Do not `curl` `/api/v1/components/` until Epic 2 ships REST.

## AD-5 fallback (non-default)

Default remains the **runtime contrib plugin** already shipped (story 1.2).
The AD-5 fallback is **non-default** and is not the starting plan.

Use it only if a later story cannot inject picker/chips into the pinned front
tag: an isolated front image built from the **matching official source tag**
plus a patch file **in this repo**. That is a front-from-source rebuild, not a
vendor of `taiga-front`, and not a Taiga source merge. If it is ever used,
record the fact **in this same `UPGRADE.md`**. Do not start that rebuild from
this playbook.

## Rollback

```bash
cd /path/to/taiga-docker
rm docker-compose.override.yml
docker compose down
docker compose up -d
```

Addon tables (once Epic 2 exists) remain unused in Postgres (FR-5). Do not
invent `DROP` scripts.
