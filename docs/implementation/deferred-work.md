# Deferred Work

## Deferred from: code review of 1-1-overlay-scaffolding (2026-08-17)

- **`TAIGA_PIN=latest` is not blocked.** Nothing prevents `--build-arg TAIGA_PIN=latest` or `TAIGA_PIN=latest docker compose build`, which AD-2 forbids. The existing `:latest` assertions only scan Dockerfile source text, not the resolved build arg or the rendered compose image tag. [platform/back.Dockerfile:5, platform/front.Dockerfile:5]

- **README is bash-only.** `cp` and the compose snippets in `platform/README.md` have no PowerShell/Windows equivalent. Deferred because operators run `taiga-docker` on Linux; revisit if a Windows operator is in scope. [platform/README.md]

- **`test_override_does_not_replace_official_config_files` is a whole-file substring scan.** ~~It asserts `"config.py"`, `"conf.json"`, `"INSTALLED_APPS"`, `"contribPlugins"` are absent from the entire override file including comments.~~ **Resolved in 1.2** — the test now asserts no compose volume maps those files and `taiga-async` still has no `entrypoint`/`command`. [tests/test_overlay_scaffolding.py]

- **AC-4 live login was not executed.** Docker is not installed on the implementation machine. Story **1.3** closed the operator path: login is a **manual glance** in `platform/UPGRADE.md`. Automated credentialed login is owned by **3-1-project-settings-catalog-ui** (first Epic 3 story; catalog UI is the first authenticated Addon surface). [docs/implementation/1-1-overlay-scaffolding.md, platform/UPGRADE.md, docs/planning/epics.md]

## Deferred from: story 1-2-plugin-load-without-replacing-official-config (2026-08-17)

- **AC-3 live container inspect was not executed.** Docker is not installed. Static tests prove registry parsing, overlay import-then-append, Dockerfile COPY/hook order, stub import, and front JSON mutate contract. `test_live_overlay_images_load_stub_when_docker_present` and the jq-driven script run are `skipif`. Story **1.3** shipped `platform/smoke.py` (fixture fail-closed + live `docker compose exec`). Live still `skipif` when Docker or a running overlay stack is absent. [tests/test_plugin_load.py, platform/smoke.py, tests/test_upgrade_playbook.py]

## Deferred from: code review of 1-2-plugin-load-without-replacing-official-config (2026-08-17)

- **`apk add --no-cache jq` is unpinned.** `platform/front.Dockerfile` installs `jq` from whatever version Alpine's repo serves at build time, and adds a network dependency to every front build. This sits in tension with the pin discipline story 1.1 established for `TAIGA_PIN` (no `:latest`, single declared seed). Deferred because pinning an Alpine package version is itself fragile — pinned versions age out of the repo and break builds harder than a floating `jq` does. Revisit if front builds ever need to be byte-reproducible. [platform/front.Dockerfile]

## Deferred from: code review of 1-3-upgrade-playbook-and-smoke-test (2026-08-17)

- **Live smoke code path has no test seam.** `_run_live` JSON parsing, the `--apps-file`/`--conf-file` XOR guard, and the unreadable-`addons.txt` branch are unreachable without Docker because the tests shell out to the script. An injectable exec callable would make AC-2's live contract provable offline. Deferred because the story explicitly accepted `skipif` honesty over a refactor. [platform/smoke.py:104-174, tests/test_upgrade_playbook.py]

- **Playbook needle depends on an ASCII apostrophe in a file that mixes encodings.** `test_upgrade_playbook_states_core_migrations_are_official` asserts the exact string `core Taiga migrations are Official Taiga's`, while `platform/UPGRADE.md` uses curly `’` at lines 4, 25 and 57. Any editor auto-formatting that one line fails the suite with a message pointing at content, not punctuation. The Debug Log records this class of breakage once already. [platform/UPGRADE.md:5, tests/test_upgrade_playbook.py:85]

- **`git pull --ff-only` has no stated precondition or recovery.** Step 2 assumes a clean, non-diverged `taiga-docker` checkout. If the operator has local modifications the pull aborts mid-playbook with no documented next step. Deferred as an operator-environment concern rather than an overlay defect. [platform/UPGRADE.md:28-33]

- **Story 1.3 spec carries a wrong baseline test count.** The "Files being modified" table claims `tests/test_plugin_load.py` is "37 passed, 3 skipped"; it is actually 17 passed, 2 skipped, both before and after this commit. Nothing regressed — the spec's recorded baseline was simply wrong. Worth correcting before it is copied into a future story's "previous story intelligence". [docs/implementation/1-3-upgrade-playbook-and-smoke-test.md]

Eighteen [Patch] review findings from the same review were resolved in the 2026-08-17 follow-up (rollback honesty, live compose dir, `.env` expansion, empty-slug fail-closed, pull prohibition, seed 404, exec vs env exits, subprocess timeouts, wait-after-up, ordered needles, merge re-check, overlay identity assert, corrupted `contribPlugins`, `pg_dump` guard, crash-consistent snapshot, build-fail stop, AC-4 owning story, README attach-only). See the story file Change Log.
