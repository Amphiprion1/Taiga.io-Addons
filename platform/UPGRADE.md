# Upgrade playbook

Rehearse an Official Taiga bump. There is **no Taiga source merge** in this repo
(NFR-1). You update the operator’s official `taiga-docker` checkout and rebuild
two overlay images from one explicit pin. **core Taiga migrations are Official Taiga's** — this overlay never vendors or runs a substitute `migrate` for core.

Do not volume-map a full `config.py` or `conf.json`. Append-not-replace stays
in force (AD-3).

`TAIGA_ADDONS_ROOT` and `POSTGRES_USER` live in official `taiga-docker/.env`.
They are empty in a bare shell. From that directory, load them before any
command that expands those variables on the host:

```bash
set -a
. ./.env
set +a
```

## 1. Backup the database

Do this first. User and database names come from official `.env`
(`POSTGRES_USER`, typically `taiga`). Do not invent a second database.
Expand `POSTGRES_USER` **inside** the db container — a host `$POSTGRES_USER`
is empty unless you sourced `.env`.

```bash
# from official taiga-docker/
set -euo pipefail
outfile="taiga-backup-$(date +%Y%m%d%H%M%S).sql"
if ! docker compose exec -T taiga-db sh -c 'pg_dump -U "$POSTGRES_USER" taiga' > "$outfile"; then
  rm -f "$outfile"
  echo "pg_dump failed; aborting. Do not continue without a good dump." >&2
  exit 1
fi
```

The second-precision stamp avoids clobbering a same-day retry. The `if !`
plus `rm -f` drops a truncated file if `pg_dump` fails — a bare `>` redirect
would leave that file looking like a dump.

A Postgres volume snapshot is **not** an equal alternative while the DB is
running: it is **not crash-consistent**. Only snapshot after
`docker compose stop taiga-db` (or the whole stack). Prefer `pg_dump`.

Keep the dump until smoke passes. It is disaster recovery, not a rollback
button — see Rollback.

## 2. Pull official compose updates

Update the operator’s official `taiga-docker` git checkout on the **`stable`**
branch (not `main`). Preserve `.env` and `docker-compose.override.yml`.

```bash
cd /path/to/taiga-docker
git fetch origin
git checkout stable
git pull --ff-only origin stable
docker compose -f docker-compose.yml -f docker-compose.override.yml config
```

Re-run that 1.1 merge verification after every `git pull`. An upstream
service rename silently invalidates the override; `config` fails closed
before you bump the pin.

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
both Hub tags always exist. Concretely, **`taigaio/taiga-front:6.10.2` is a
404** on Hub today (verified 2026-08-17). Shared tags that exist on both
images include `6.9.0`, `6.8.2`, `6.8.1`, `6.7.1`, `6.7.0`, `6.6.0`. Building
the seed as-is will fail at the front `FROM` until you choose a shared tag.

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
set -euo pipefail
docker compose build || exit 1
docker compose up -d --wait
```

If `docker compose build` fails, **stop**. Do not `up -d` the previous
overlay images against a half-bumped pin.

`--wait` blocks until compose healthchecks pass. Official entrypoint
`migrate` runs on boot during this wait. Do not smoke mid-migrate — a
partial boot looks like "no running overlay". If your compose is too old
for `--wait`, retry `docker compose exec -T taiga-back true` with `sleep 5`
until it succeeds (or give up after ~5 minutes).

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

Once that migrate has run, the bump is one-way for schema. See Rollback.

## 6. Smoke

### Automated stub load (now)

From official `taiga-docker/` so compose finds the project. Source `.env`
first (`TAIGA_ADDONS_ROOT` is a compose key, not a login-shell variable):

```bash
set -a
. ./.env
set +a
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

### Catalog REST glance

After stub smoke, confirm the project catalog is reachable (authenticated
member or admin; replace `<token>` and `<id>`). Official `.env` does not
define `TAIGA_URL`. After sourcing it (step 6 header), derive the public
origin from `TAIGA_SCHEME` and `TAIGA_DOMAIN`:

```bash
: "${TAIGA_URL:=${TAIGA_SCHEME:-http}://${TAIGA_DOMAIN:-localhost:9000}}"
code=$(curl -sS -o /tmp/taiga-components-glance.json -w "%{http_code}" \
  -H "Authorization: Bearer <token>" \
  "$TAIGA_URL/api/v1/components?project=<id>")
test "$code" = "200"
```

A bare `curl -sS` exits 0 on 401/403/404/500. The `%{http_code}` write-out
plus `test` fails the glance if the route is unregistered or the token is
wrong.

### Later operator glances (Epic 3 — not automated yet)

When catalog / picker / chips exist, glance these after stub smoke. They are
**not** automated checks in this playbook:

- Login still works (operator UI glance; not a credentialed script)
- Project settings → Components catalog
- User Story detail → picker
- Kanban / backlog → chips

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

A pin bump is **one-way** once official core `migrate` has run (step 5, on
boot). The commands below only remove the overlay override and cycle official
images. They **do not undo** core or Addon migrations. The dump from step 1
is **disaster recovery, not a routine rollback**. Restore from that dump only
if you must recover the pre-bump database.

```bash
cd /path/to/taiga-docker
rm docker-compose.override.yml
docker compose down
docker compose up -d
```

Addon tables (once Epic 2 exists) remain unused in Postgres (FR-5). Do not
invent `DROP` scripts.
