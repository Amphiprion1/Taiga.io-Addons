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

## Rollback

```bash
cd /path/to/taiga-docker
rm docker-compose.override.yml
docker compose down
docker compose up -d
```

Plugin load (`INSTALLED_APPS` / `contribPlugins`) is story **1.2**, not this file.
