# Overlay image. Official taiga-back is the immutable base (AD-1, AD-2).
# Pin is a single declared value (platform/TAIGA_PIN). Override at build:
#   docker build --build-arg TAIGA_PIN=<tag> -f platform/back.Dockerfile
# 1.2: COPY platform/entrypoint-back.sh and append INSTALLED_APPS
ARG TAIGA_PIN=6.10.2
FROM taigaio/taiga-back:${TAIGA_PIN}
