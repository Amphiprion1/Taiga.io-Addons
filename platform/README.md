# Overlay attach (story 1.1)

Copy `docker-compose.override.yml` into your official `taiga-docker` directory. Do not edit official `docker-compose.yml`.

The declared pin is **`platform/TAIGA_PIN`** (seed **6.10.2**). Every `${TAIGA_PIN:-…}` default and Dockerfile `ARG` default must match that file. Set `TAIGA_PIN` in the official `.env` if your production official tag differs.

## Apply

Append the two lines from `platform/compose.env.example` to official `taiga-docker/.env` (Compose auto-loads `.env`; do not replace official keys):

```bash
# this repo
# official taiga-docker checkout
cp /absolute/path/to/Taiga.io-addons/platform/docker-compose.override.yml /path/to/taiga-docker/
cd /path/to/taiga-docker

# verify official compose is untouched and the merge is valid
docker compose -f docker-compose.yml -f docker-compose.override.yml config

docker compose build
docker compose up -d
```

`TAIGA_ADDONS_ROOT` must be set in `.env` or every `docker compose` command (`down`, `logs`, `ps`, `restart`) fails interpolation. A one-shot `export` is not enough.

Overlay images are **local-only**. Do not run `docker compose pull` — `taiga-addons-back` / `taiga-addons-front` are not on a registry. `taiga-async` reuses the back image (`pull_policy: never`).

What changes: `taiga-back` and `taiga-async` share image `taiga-addons-back:<pin>` (`FROM taigaio/taiga-back:<pin>`). `taiga-front` becomes `taiga-addons-front:<pin>`. Gateway, Postgres, events, and protected stay official.

Login to Taiga on a healthy stack is the operator smoke check (story **1.3**). This story only ships the attach path.

## Plugin load (append, do not replace)

Enabled slugs live in `platform/addons.txt` (comments and blank lines ignored). That file is the single enable switch: both overlay images `COPY` the whole `addons/` tree and install only listed slugs at build time. Add an Addon with `addons/<slug>/{back,front}` + one line + rebuild. Each slug is appended to official config — official `.env` URLs and flags stay in effect.

- **Back / async:** `DJANGO_SETTINGS_MODULE=settings.overlay` is baked into `taiga-addons-back`. That module does `from .config import *` then `INSTALLED_APPS += ["taiga_contrib_<slug>"]`. Official `/taiga-back/settings/config.py` is not copied or volume-mapped. `taiga-async` reuses the same image, so it sees the same apps without an override `entrypoint`.
- **Front:** official `/docker-entrypoint.d/30_config_env_subst.sh` still writes `conf.json` from env. Overlay `/docker-entrypoint.d/40_patch-front-conf.sh` then appends `plugins/<slug>/<slug>.json` to `contribPlugins` (idempotent). Official `api` / `eventsUrl` / `baseHref` and Slack/GitHub entries are left untouched.

Do **not** volume-map a full `config.py` or `conf.json` — that ignores official env.

Stub Addon **components** ships as importable `taiga_contrib_components` plus `/usr/share/nginx/html/plugins/components/{components.json,components.js}`.

## Rollback

```bash
cd /path/to/taiga-docker
rm docker-compose.override.yml
docker compose down
docker compose up -d
```

