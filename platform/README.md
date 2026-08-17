# Overlay attach (story 1.1)

Copy `docker-compose.override.yml` into your official `taiga-docker` directory. Do not edit official `docker-compose.yml`.

Default pin is **6.10.2** (`platform/TAIGA_PIN`). Set `TAIGA_PIN` to your production official tag if it differs.

```bash
# this repo
export TAIGA_ADDONS_ROOT=/absolute/path/to/Taiga.io-addons
export TAIGA_PIN=6.10.2   # optional; defaults to 6.10.2

# official taiga-docker checkout
cp "$TAIGA_ADDONS_ROOT/platform/docker-compose.override.yml" /path/to/taiga-docker/
cd /path/to/taiga-docker
docker compose build
docker compose up -d
```

What changes: `taiga-back` and `taiga-async` share image `taiga-addons-back:<pin>` (`FROM taigaio/taiga-back:<pin>`). `taiga-front` becomes `taiga-addons-front:<pin>`. Gateway, Postgres, events, and protected stay official.

Remove the override file and `docker compose up -d` to return to stock official images.

Plugin load (`INSTALLED_APPS` / `contribPlugins`) is story **1.2**, not this file.
