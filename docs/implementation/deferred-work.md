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

- ~~**Story 1.3 spec carries a wrong baseline test count.**~~ **Corrected in 2.1.** The 1.3 "Files being modified" table claimed `tests/test_plugin_load.py` was "37 passed, 3 skipped"; the real pre-2.1 baseline is 17 passed, 2 skipped in that file and **64 passed, 4 skipped** for the whole suite. 2.1 used the corrected count and does not copy 37/3 forward. [docs/implementation/1-3-upgrade-playbook-and-smoke-test.md, docs/implementation/2-1-models-and-migrations.md]

Eighteen [Patch] review findings from the same review were resolved in the 2026-08-17 follow-up (rollback honesty, live compose dir, `.env` expansion, empty-slug fail-closed, pull prohibition, seed 404, exec vs env exits, subprocess timeouts, wait-after-up, ordered needles, merge re-check, overlay identity assert, corrupted `contribPlugins`, `pg_dump` guard, crash-consistent snapshot, build-fail stop, AC-4 owning story, README attach-only). See the story file Change Log.

## Deferred from: story 2-1-models-and-migrations (2026-08-18)

- **AC-1 live container migrate was not executed.** Docker is not on PATH and no overlay stack is running. Layer B ran official `migrate` against Django 3.2.25 + SQLite (tables, `(project_id, lower(name))` unique, assignment unique, Component delete cascades Assignments only, `migrate … zero` reverse). Live `showmigrations taiga_contrib_components` and `makemigrations --check --dry-run` stay `skipif`. [tests/test_components_models.py]

## Deferred from: code review of story-2.1 (2026-08-18)

- **SQLite `lower()` is ASCII-only; production Postgres folds per database collation.** Layer B proves AC-3 only for ASCII pairs (`"API"`/`"api"`, `"Front"`/`"FRONT"`). `Component(name="ÉTUDE")` and `Component(name="étude")` collide on Postgres but both insert on SQLite — the one case where the two engines genuinely disagree is the case the suite cannot see. Needs a Postgres-backed run to close. [tests/test_components_models.py:390, 452-455]

- **`Component.save()` name normalization is a convention, not an invariant.** `bulk_create`, `QuerySet.update()`, `raw`, future data migrations, and `save(update_fields=[...])` omitting `"name"` all bypass the strip, so `"  API  "` and `"API"` can coexist in one project — the index is on `lower(name)`, not `lower(btrim(name))`, by design. Empty and whitespace-only names are likewise accepted at every layer (no `CHECK (length(btrim(name)) > 0)`). Out of 2.1's AC set: FR-6 maps to 2.2 and 3.1 (`docs/planning/epics.md:72`), which own serializer validation. Flagged so 2.2 does not assume the model layer already guarantees trimmed/non-empty. [addons/components/back/taiga_contrib_components/models.py:11, 17-20]

- **The `RunSQL` `lower(name)` index is invisible to Django's migration state.** `makemigrations --check --dry-run` compares model state and `RunSQL` contributes none, so renaming `Component.name`, adding `db_table`, or changing `max_length` would pass the drift check while silently breaking AC-3's index. Inherent to expressing the index as raw SQL (Django 3.2 cannot declare it); worth a comment in the migration at minimum. [addons/components/back/taiga_contrib_components/migrations/0001_initial.py:82-90]

- **The addon package fence is a per-filename blacklist, not an allowlist.** 2.1 correctly retired `assert not (STUB_APP / "models.py").exists()`, leaving only `urls.py` asserted absent. A future story adding `serializers.py`, `views.py`, `admin.py`, or `permissions.py` — all out of scope for 2.1 — would draw no objection from any test. Asserting the package's file set against an allowlist would survive the operations nobody thought of. [tests/test_plugin_load.py:267]

- **Cross-project Assignment is not prevented at any layer — decide before 2.3 opens write paths.** The unique constraint is `(userstory, component)` only, so a UserStory in project A can be assigned a Component owned by project B: both FKs resolve, uniqueness is satisfied, the row persists. No AC in 2.1 covers it, and the project-scoped queries in 2.2/2.3/3.2/3.3 will all assume it cannot happen. [addons/components/back/taiga_contrib_components/models.py:33-41]

  **Why this is not "just validation, 2.3 owns it."** FR-6 trimming produces an ugly but meaningful row that a later serializer can normalize. This produces *incoherent* data, and no later layer can repair it — given a story in project A holding a component from project B, there is no correct answer to which project owns the truth. Rows admitted by the model layer are permanent. The cost is asymmetric: closing it now, against empty tables and an unreleased migration, is nearly free; closing it after 2.2/2.3 ship write paths costs a data migration *plus* a repair policy for whatever is already there.

  **Why it was not simply patched in 2.1.** No cheap airtight fix exists. A Postgres `CHECK` cannot span tables. A trigger means DDL the overlay exists to avoid (NFR-4). `Model.clean()` is bypassed by `bulk_create` / `QuerySet.update()` / raw SQL, i.e. the same non-invariant that already makes `Component.save()` stripping a convention rather than a guarantee.

  **Trap for whoever picks this up:** the obvious fix — denormalize `project_id` onto Assignment and add a composite constraint — is not obviously correct. Taiga supports moving a UserStory between projects; a denormalized `project_id` goes stale on that move, and the invariant becomes its own source of bugs. Any real fix has to state what happens to existing Assignments when a story changes project (cascade-delete them? re-point them? block the move?). That question is the actual decision, and it is a product question as much as a schema one.
