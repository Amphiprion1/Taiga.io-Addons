# Overlay image. Official taiga-back is the immutable base (AD-1, AD-2).
# Default ARG matches platform/TAIGA_PIN (tests enforce the copies).
# ARG before FROM is not in scope after FROM — redeclared below for later
# instructions (story 1.2). Do not reference ${TAIGA_PIN} between FROM and
# the second ARG; it would expand empty.
ARG TAIGA_PIN=6.10.2
FROM taigaio/taiga-back:${TAIGA_PIN}
ARG TAIGA_PIN

# Append-only: official /taiga-back/settings/config.py is not overwritten.
COPY platform/addons.txt /opt/taiga-addons/addons.txt
COPY addons/components/back/taiga_contrib_components /taiga-back/taiga_contrib_components
COPY platform/overlay.py /taiga-back/settings/overlay.py
COPY platform/entrypoint-back.sh /opt/taiga-addons/entrypoint-back.sh
RUN chmod +x /opt/taiga-addons/entrypoint-back.sh
ENV DJANGO_SETTINGS_MODULE=settings.overlay
