# Deferred Work

## Deferred from: code review of 1-1-overlay-scaffolding (2026-08-17)

- **`TAIGA_PIN=latest` is not blocked.** Nothing prevents `--build-arg TAIGA_PIN=latest` or `TAIGA_PIN=latest docker compose build`, which AD-2 forbids. The existing `:latest` assertions only scan Dockerfile source text, not the resolved build arg or the rendered compose image tag. [platform/back.Dockerfile:5, platform/front.Dockerfile:5]

- **README is bash-only.** `cp` and the compose snippets in `platform/README.md` have no PowerShell/Windows equivalent. Deferred because operators run `taiga-docker` on Linux; revisit if a Windows operator is in scope. [platform/README.md]

- **`test_override_does_not_replace_official_config_files` is a whole-file substring scan.** ~~It asserts `"config.py"`, `"conf.json"`, `"INSTALLED_APPS"`, `"contribPlugins"` are absent from the entire override file including comments.~~ **Resolved in 1.2** — the test now asserts no compose volume maps those files and `taiga-async` still has no `entrypoint`/`command`. [tests/test_overlay_scaffolding.py]

- **AC-4 live login was not executed.** Docker is not installed on the implementation machine. "Login to Taiga still works on a healthy stack" is deferred to story **1.3** (upgrade playbook and smoke test). This story ships the attach path and a static/config-merge proof only. [docs/implementation/1-1-overlay-scaffolding.md]

## Deferred from: story 1-2-plugin-load-without-replacing-official-config (2026-08-17)

- **AC-3 live container inspect was not executed.** Docker is not installed. Static tests prove registry parsing, overlay import-then-append, Dockerfile COPY/hook order, stub import, and front JSON mutate contract. `test_live_overlay_images_load_stub_when_docker_present` and the jq-driven script run are `skipif`. Live import + plugin path + `conf.json` keys belong to **1.3** smoke. [tests/test_plugin_load.py]

## Deferred from: code review of 1-2-plugin-load-without-replacing-official-config (2026-08-17)

- **`apk add --no-cache jq` is unpinned.** `platform/front.Dockerfile` installs `jq` from whatever version Alpine's repo serves at build time, and adds a network dependency to every front build. This sits in tension with the pin discipline story 1.1 established for `TAIGA_PIN` (no `:latest`, single declared seed). Deferred because pinning an Alpine package version is itself fragile — pinned versions age out of the repo and break builds harder than a floating `jq` does. Revisit if front builds ever need to be byte-reproducible. [platform/front.Dockerfile]
