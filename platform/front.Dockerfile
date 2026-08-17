# Overlay image. Official taiga-front is the immutable base (AD-1, AD-2).
# Default ARG matches platform/TAIGA_PIN (tests enforce the copies).
# ARG before FROM is not in scope after FROM — redeclared below for later
# instructions (story 1.2). Do not reference ${TAIGA_PIN} between FROM and
# the second ARG; it would expand empty.
ARG TAIGA_PIN=6.10.2
FROM taigaio/taiga-front:${TAIGA_PIN}
ARG TAIGA_PIN

# Official 30_config_env_subst.sh stays. 40_ mutates contribPlugins only.
# Whole addons/ tree + addons.txt; build fans out enabled slugs (AD-9).
RUN apk add --no-cache jq
COPY platform/addons.txt /opt/taiga-addons/addons.txt
COPY addons /opt/taiga-addons/src
COPY platform/install-enabled-addons.sh /opt/taiga-addons/install-enabled-addons.sh
COPY platform/patch-front-conf.sh /docker-entrypoint.d/40_patch-front-conf.sh
RUN chmod +x /opt/taiga-addons/install-enabled-addons.sh \
        /docker-entrypoint.d/40_patch-front-conf.sh \
    && /opt/taiga-addons/install-enabled-addons.sh front
