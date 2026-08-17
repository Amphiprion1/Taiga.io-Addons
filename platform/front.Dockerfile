# Overlay image. Official taiga-front is the immutable base (AD-1, AD-2).
# Pin is a single declared value (platform/TAIGA_PIN). Override at build:
#   docker build --build-arg TAIGA_PIN=<tag> -f platform/front.Dockerfile
# 1.2: COPY plugins and append contribPlugins
ARG TAIGA_PIN=6.10.2
FROM taigaio/taiga-front:${TAIGA_PIN}
