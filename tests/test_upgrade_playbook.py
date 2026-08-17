"""Story 1.3 — upgrade playbook needles + fail-closed stub-load smoke."""

from __future__ import annotations

import ast
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLATFORM = REPO / "platform"
UPGRADE = PLATFORM / "UPGRADE.md"
README = PLATFORM / "README.md"
SMOKE = PLATFORM / "smoke.py"
ADDONS_TXT = PLATFORM / "addons.txt"
OVERLAY_PY = PLATFORM / "overlay.py"
DEFERRED = REPO / "docs" / "implementation" / "deferred-work.md"
THIS_TEST = Path(__file__).resolve()
COMPOSE_DIR = os.environ.get("TAIGA_DOCKER")
SUBPROCESS_TIMEOUT = 60


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_smoke(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE), *args],
        capture_output=True,
        text=True,
        check=check,
        cwd=str(REPO),
        timeout=SUBPROCESS_TIMEOUT,
    )


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _import_platform(name: str):
    sys.path.insert(0, str(PLATFORM))
    try:
        return importlib.import_module(name)
    finally:
        if sys.path and sys.path[0] == str(PLATFORM):
            sys.path.pop(0)


def _positions_in_order(text: str, needles: list[str]) -> None:
    pos = -1
    for needle in needles:
        found = text.find(needle, pos + 1)
        assert found != -1, f"{needle!r} missing or out of order after {pos}"
        pos = found


OFFICIALISH_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "taiga.base",
    "taiga.projects",
    "taiga_contrib_slack",
]

PASS_APPS = [*OFFICIALISH_APPS, "taiga_contrib_components"]

PASS_CONF = {
    "api": "http://taiga-gateway/api/v1/",
    "eventsUrl": "ws://taiga-gateway/events",
    "baseHref": "/",
    "contribPlugins": [
        "plugins/slack/slack.json",
        "plugins/components/components.json",
    ],
}


# --- UPGRADE.md needles (AC-1) ------------------------------------------------


def test_upgrade_playbook_exists():
    assert UPGRADE.is_file()


def test_upgrade_playbook_has_operator_sequence_needles():
    text = _read(UPGRADE)
    lower = text.lower()
    assert "pg_dump" in text or "backup" in lower
    assert "git" in lower
    assert "taiga-docker" in text
    assert "stable" in lower
    assert "TAIGA_PIN" in text
    assert "docker compose build" in text
    assert "up -d" in text
    assert "entrypoint" in lower or "migrate" in lower
    assert "smoke" in lower


def test_upgrade_playbook_operator_sequence_is_ordered():
    """Needles must appear in operator order, not as a bag of substrings."""
    body = _read(UPGRADE).split("## Rollback")[0]
    _positions_in_order(
        body,
        [
            "pg_dump",
            "git pull",
            "-f docker-compose.yml -f docker-compose.override.yml config",
            "TAIGA_PIN",
            "docker compose build",
            "up -d",
            "smoke.py",
        ],
    )
    headings = [
        "## 1. Backup",
        "## 2. Pull official",
        "## 3. Bump",
        "## 4. Rebuild",
        "## 5. Addon migrate",
        "## 6. Smoke",
    ]
    _positions_in_order(body, headings)


def test_upgrade_playbook_states_core_migrations_are_official():
    text = _read(UPGRADE)
    assert "core Taiga migrations are Official Taiga's" in text
    assert "no Taiga source merge" in text


def test_upgrade_playbook_documents_ad5_as_non_default():
    text = _read(UPGRADE)
    lower = text.lower()
    assert "AD-5" in text
    assert "front-from-source" in lower or "front from source" in lower
    assert "fallback" in lower
    assert "non-default" in lower or "not the default" in lower


def test_upgrade_playbook_forbids_overlay_compose_pull():
    text = _read(UPGRADE)
    assert not re.search(r"^[ \t]*docker compose pull\b", text, re.M), (
        "playbook must not instruct a blanket docker compose pull"
    )
    assert re.search(r"do not.{0,80}docker compose pull", text, re.I | re.S)
    assert "taiga-addons-back" in text or "overlay" in text.lower()
    assert "pull_policy" in text or "never" in text.lower() or "local-only" in text.lower()


def test_upgrade_playbook_one_pin_two_images_and_copies():
    text = _read(UPGRADE)
    assert "taiga-back" in text
    assert "taiga-front" in text
    assert ":latest" in text
    assert "compose.env.example" in text or "${TAIGA_PIN" in text or "ARG" in text


def test_upgrade_playbook_rollback_is_not_migration_undo():
    text = _read(UPGRADE)
    rollback = text.split("## Rollback", 1)[1]
    lower = rollback.lower()
    assert "disaster recovery" in lower or "one-way" in lower
    assert "does not undo" in lower or "not a routine rollback" in lower
    assert "migrate" in lower or "migration" in lower


def test_upgrade_playbook_sources_compose_env_not_bare_shell():
    text = _read(UPGRADE)
    assert re.search(r"(source|\.)\s+\.?/?\.env", text)
    assert "sh -c" in text
    assert "'pg_dump -U \"$POSTGRES_USER\" taiga'" in text or (
        'pg_dump -U "$POSTGRES_USER"' in text and "sh -c" in text
    )
    assert "TAIGA_ADDONS_ROOT" in text


def test_upgrade_playbook_documents_broken_seed_front_tag():
    text = _read(UPGRADE)
    assert "taiga-front:6.10.2" in text
    assert "404" in text
    assert "6.9.0" in text


def test_upgrade_playbook_waits_after_up_before_smoke():
    body = _read(UPGRADE).split("## Rollback")[0]
    rebuild = body.split("## 4. Rebuild", 1)[1].split("## 5.", 1)[0]
    assert "--wait" in rebuild or re.search(r"\bsleep\b", rebuild)
    smoke = body.split("## 6. Smoke", 1)[1]
    assert "wait" in (rebuild + smoke).lower()


def test_upgrade_playbook_rechecks_compose_merge_after_git_pull():
    step2 = _read(UPGRADE).split("## 2.", 1)[1].split("## 3.", 1)[0]
    assert "-f docker-compose.yml -f docker-compose.override.yml config" in step2


def test_upgrade_playbook_stops_if_build_fails():
    rebuild = _read(UPGRADE).split("## 4. Rebuild", 1)[1].split("## 5.", 1)[0]
    assert re.search(r"build.*fail|fail.*build", rebuild, re.I)
    assert re.search(r"do not.*up -d|stop", rebuild, re.I)
    assert "|| exit" in rebuild or "set -e" in rebuild


def test_upgrade_playbook_pg_dump_does_not_clobber_or_keep_failed_dump():
    backup = _read(UPGRADE).split("## 1. Backup", 1)[1].split("## 2.", 1)[0]
    assert "%Y%m%d%H%M%S" in backup
    assert "rm -f" in backup or "pg_dump failed" in backup.lower()
    assert "set -e" in backup or "if !" in backup


def test_upgrade_playbook_volume_snapshot_is_not_equal_to_dump():
    backup = _read(UPGRADE).split("## 1. Backup", 1)[1].split("## 2.", 1)[0].lower()
    assert "crash-consistent" in backup or "not crash" in backup
    assert "stop" in backup
    assert "not" in backup and ("equal" in backup or "alternative" in backup or "prefer" in backup)


def test_readme_links_upgrade_and_smoke():
    text = _read(README)
    assert "UPGRADE.md" in text
    assert "smoke.py" in text
    assert re.search(r"(source|\.)\s+\.?/?\.env", text)
    assert "this story only ships the attach path" not in text.lower()


def test_deferred_work_ac4_names_owning_story():
    text = _read(DEFERRED)
    assert "3-1-project-settings-catalog-ui" in text or "3.1" in text
    assert "AC-4" in text


# --- smoke.py contract (AC-2) -------------------------------------------------


def test_smoke_reuses_overlay_helpers_not_a_copy():
    overlay_mod = _import_platform("overlay")
    smoke_mod = _import_platform("smoke")
    assert smoke_mod.overlay is overlay_mod
    assert smoke_mod.overlay.parse_addon_slugs is overlay_mod.parse_addon_slugs
    assert smoke_mod.overlay.contrib_app_label is overlay_mod.contrib_app_label
    assert smoke_mod.overlay.contrib_plugin_path is overlay_mod.contrib_plugin_path
    text = _read(SMOKE)
    assert r"^[a-z][a-z0-9_]*$" not in text
    overlay_src = _read(OVERLAY_PY)
    assert "def parse_addon_slugs" in overlay_src
    assert "def contrib_app_label" in overlay_src
    assert "def contrib_plugin_path" in overlay_src


def test_smoke_fixture_fails_when_addon_app_missing(tmp_path):
    apps = _write_json(tmp_path / "apps.json", OFFICIALISH_APPS)
    conf = _write_json(tmp_path / "conf.json", PASS_CONF)
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode != 0
    assert "taiga_contrib_components" in result.stderr


def test_smoke_fixture_fails_when_plugin_missing(tmp_path):
    apps = _write_json(tmp_path / "apps.json", PASS_APPS)
    conf = _write_json(
        tmp_path / "conf.json",
        {**PASS_CONF, "contribPlugins": ["plugins/slack/slack.json"]},
    )
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode != 0
    assert "plugins/components/components.json" in result.stderr


def test_smoke_fixture_fails_when_contrib_plugins_empty(tmp_path):
    apps = _write_json(tmp_path / "apps.json", PASS_APPS)
    conf = _write_json(tmp_path / "conf.json", {**PASS_CONF, "contribPlugins": []})
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode != 0
    assert "plugins/components/components.json" in result.stderr


def test_smoke_fixture_passes_when_stub_is_loaded(tmp_path):
    apps = _write_json(tmp_path / "apps.json", PASS_APPS)
    conf = _write_json(tmp_path / "conf.json", PASS_CONF)
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode == 0, result.stderr


def test_smoke_fixture_reports_both_missing_at_once(tmp_path):
    apps = _write_json(tmp_path / "apps.json", OFFICIALISH_APPS)
    conf = _write_json(tmp_path / "conf.json", {**PASS_CONF, "contribPlugins": []})
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode != 0
    assert "taiga_contrib_components" in result.stderr
    assert "plugins/components/components.json" in result.stderr


def test_smoke_fails_closed_when_addons_txt_has_no_slugs(tmp_path):
    empty = tmp_path / "addons.txt"
    empty.write_text("# nothing enabled\n\n", encoding="utf-8")
    apps = _write_json(tmp_path / "apps.json", PASS_APPS)
    conf = _write_json(tmp_path / "conf.json", PASS_CONF)
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(empty),
    )
    assert result.returncode != 0
    err = result.stderr.lower()
    assert "no enabled" in err or "empty" in err


def test_smoke_fails_when_contrib_plugins_is_not_a_list(tmp_path):
    apps = _write_json(tmp_path / "apps.json", PASS_APPS)
    conf = _write_json(
        tmp_path / "conf.json",
        {**PASS_CONF, "contribPlugins": "plugins/components/components.json"},
    )
    result = _run_smoke(
        "--apps-file",
        str(apps),
        "--conf-file",
        str(conf),
        "--addons-file",
        str(ADDONS_TXT),
    )
    assert result.returncode != 0
    err = result.stderr.lower()
    assert "contribplugins" in err
    assert "not a list" in err or "corrupt" in err
    assert "missing contribplugins:" not in err


def test_smoke_subprocess_calls_use_timeout():
    smoke_mod = _import_platform("smoke")
    assert getattr(smoke_mod, "SUBPROCESS_TIMEOUT", 0) > 0
    tree = ast.parse(_read(SMOKE))
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == "run")
            or (isinstance(node.func, ast.Name) and node.func.id == "run")
        )
    ]
    assert runs, "smoke.py must call subprocess.run"
    for node in runs:
        names = {kw.arg for kw in node.keywords}
        assert "timeout" in names, "every subprocess.run must pass timeout="
    test_src = _read(THIS_TEST)
    assert "timeout=" in test_src
    assert "TAIGA_DOCKER" in test_src


def test_live_smoke_uses_taiga_docker_compose_dir_not_repo():
    src = _read(THIS_TEST)
    assert "TAIGA_DOCKER" in src
    assert "cwd=str(REPO)" not in src.split("def _overlay_exec_available")[1].split(
        "def test_live_smoke_when_overlay_stack_running"
    )[0]
    smoke_src = _read(SMOKE)
    assert "--compose-dir" in smoke_src
    assert "TAIGA_DOCKER" in smoke_src


def _overlay_exec_available() -> bool:
    if shutil.which("docker") is None:
        return False
    if not COMPOSE_DIR:
        return False
    if not (Path(COMPOSE_DIR) / "docker-compose.yml").is_file():
        return False
    try:
        probe = subprocess.run(
            ["docker", "compose", "exec", "-T", "taiga-back", "true"],
            capture_output=True,
            text=True,
            cwd=COMPOSE_DIR,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_live_smoke_when_overlay_stack_running():
    """AC-2 live exec. skipif Docker absent or compose cannot reach taiga-back."""
    if not COMPOSE_DIR:
        pytest.skip(
            "TAIGA_DOCKER unset; live smoke needs official taiga-docker compose project"
        )
    if not _overlay_exec_available():
        pytest.skip("overlay stack not running (compose exec taiga-back failed)")
    result = _run_smoke("--compose-dir", COMPOSE_DIR)
    assert result.returncode == 0, result.stderr
