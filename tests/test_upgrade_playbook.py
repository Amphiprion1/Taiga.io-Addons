"""Story 1.3 — upgrade playbook needles + fail-closed stub-load smoke."""

from __future__ import annotations

import json
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_smoke(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE), *args],
        capture_output=True,
        text=True,
        check=check,
        cwd=str(REPO),
    )


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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
    assert "docker compose pull" in text
    assert "taiga-addons-back" in text or "overlay" in text.lower()
    assert "pull_policy" in text or "never" in text.lower() or "local-only" in text.lower()


def test_upgrade_playbook_one_pin_two_images_and_copies():
    text = _read(UPGRADE)
    assert "taiga-back" in text
    assert "taiga-front" in text
    assert ":latest" in text
    assert "compose.env.example" in text or "${TAIGA_PIN" in text or "ARG" in text


def test_readme_links_upgrade_and_smoke():
    text = _read(README)
    assert "UPGRADE.md" in text
    assert "smoke.py" in text


# --- smoke.py contract (AC-2) -------------------------------------------------


def test_smoke_reuses_overlay_helpers_not_a_copy():
    text = _read(SMOKE)
    assert "parse_addon_slugs" in text
    assert "contrib_app_label" in text
    assert "contrib_plugin_path" in text
    assert "import overlay" in text or "from overlay import" in text
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


def _overlay_exec_available() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(
        ["docker", "compose", "exec", "-T", "taiga-back", "true"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    return probe.returncode == 0


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_live_smoke_when_overlay_stack_running():
    """AC-2 live exec. skipif Docker absent or compose cannot reach taiga-back."""
    if not _overlay_exec_available():
        pytest.skip("overlay stack not running (compose exec taiga-back failed)")
    result = _run_smoke()
    assert result.returncode == 0, result.stderr
