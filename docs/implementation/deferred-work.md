# Deferred Work

## Deferred from: code review of 1-1-overlay-scaffolding (2026-08-17)

- **`TAIGA_PIN=latest` is not blocked.** Nothing prevents `--build-arg TAIGA_PIN=latest` or `TAIGA_PIN=latest docker compose build`, which AD-2 forbids. The existing `:latest` assertions only scan Dockerfile source text, not the resolved build arg or the rendered compose image tag. [platform/back.Dockerfile:5, platform/front.Dockerfile:5]

- **README is bash-only.** `export` and `cp` in `platform/README.md` have no PowerShell/Windows equivalent. Deferred because operators run `taiga-docker` on Linux; revisit if a Windows operator is in scope. [platform/README.md:7-17]

- **`test_override_does_not_replace_official_config_files` is a whole-file substring scan.** It asserts `"config.py"`, `"conf.json"`, `"INSTALLED_APPS"`, `"contribPlugins"` are absent from the entire override file including comments. It will false-positive on an innocuous comment and will need rework in story 1.2, which legitimately introduces those strings. [tests/test_overlay_scaffolding.py:99-104]
