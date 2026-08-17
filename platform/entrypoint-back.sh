#!/bin/sh
set -eu
# Thin wrapper. Settings are baked via DJANGO_SETTINGS_MODULE=settings.overlay.
exec /taiga-back/docker/entrypoint.sh "$@"
