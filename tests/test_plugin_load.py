"""Story 1.2 — append Addon apps/plugins without replacing official config."""

from __future__ import annotations

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
BACK_DF = PLATFORM / "back.Dockerfile"
FRONT_DF = PLATFORM / "front.Dockerfile"
ADDONS_TXT = PLATFORM / "addons.txt"
OVERLAY_PY = PLATFORM / "overlay.py"
PATCH_SH = PLATFORM / "patch-front-conf.sh"
ENTRYPOINT_BACK = PLATFORM / "entrypoint-back.sh"
STUB_BACK = REPO / "addons" / "components" / "back"
STUB_APP = STUB_BACK / "taiga_contrib_components"
STUB_FRONT = REPO / "addons" / "components" / "front"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _import_overlay():
    sys.path.insert(0, str(PLATFORM))
    try:
        sys.modules.pop("overlay", None)
        return importlib.import_module("overlay")
    finally:
        if sys.path and sys.path[0] == str(PLATFORM):
            sys.path.pop(0)


def test_addons_txt_parser_maps_components_and_ignores_noise():
    overlay = _import_overlay()
    text = _read(ADDONS_TXT)
    slugs = overlay.parse_addon_slugs(text)
    assert slugs == ["components"]
    assert overlay.contrib_app_label("components") == "taiga_contrib_components"
    assert overlay.contrib_plugin_path("components") == "plugins/components/components.json"

    noisy = "# enabled slugs\n\ncomponents  # tail comment\n# ignored\n  \n"
    assert overlay.parse_addon_slugs(noisy) == ["components"]


def test_overlay_source_imports_official_config_before_append():
    text = _read(OVERLAY_PY)
    import_idx = text.find("from .config import *")
    if import_idx < 0:
        import_idx = text.find("from settings.config import *")
    append_idx = text.find("INSTALLED_APPS")
    assert import_idx >= 0, "overlay must star-import official config"
    assert 0 <= import_idx < append_idx


def test_overlay_import_then_append_keeps_official_settings(tmp_path, monkeypatch):
    overlay = _import_overlay()
    addons = tmp_path / "addons.txt"
    addons.write_text("# comment\n\ncomponents\n", encoding="utf-8")

    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    (settings_dir / "__init__.py").write_text("", encoding="utf-8")
    (settings_dir / "config.py").write_text(
        "INSTALLED_APPS = ['django.contrib.admin', 'taiga.base']\n"
        "TAIGA_SITES_DOMAIN = 'example.test'\n"
        "SECRET_KEY = 'official-secret'\n",
        encoding="utf-8",
    )
    shutil.copy(OVERLAY_PY, settings_dir / "overlay.py")

    monkeypatch.setenv("TAIGA_ADDONS_TXT", str(addons))
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in list(sys.modules):
        if name == "settings" or name.startswith("settings."):
            del sys.modules[name]

    loaded = importlib.import_module("settings.overlay")
    assert loaded.TAIGA_SITES_DOMAIN == "example.test"
    assert loaded.SECRET_KEY == "official-secret"
    assert loaded.INSTALLED_APPS == [
        "django.contrib.admin",
        "taiga.base",
        "taiga_contrib_components",
    ]
    # idempotent
    assert overlay.append_contrib_apps(loaded.INSTALLED_APPS, ["components"]) == list(
        loaded.INSTALLED_APPS
    )


def test_back_dockerfile_copies_addons_and_bakes_overlay_settings():
    text = _read(BACK_DF)
    parts = re.split(r"^FROM .+$", text, maxsplit=1, flags=re.M)
    assert len(parts) == 2
    after = parts[1]
    arg_m = re.search(r"^ARG TAIGA_PIN\b", after, re.M)
    copy_addons = re.search(r"^COPY\s+\S*addons\.txt\s+/opt/taiga-addons/addons\.txt", after, re.M)
    copy_overlay = re.search(
        r"^COPY\s+\S*overlay\.py\s+/taiga-back/settings/overlay\.py", after, re.M
    )
    assert arg_m, "post-FROM ARG TAIGA_PIN required"
    assert copy_addons, "must COPY addons.txt after FROM"
    assert copy_overlay, "must COPY overlay.py into official settings/"
    assert arg_m.start() < copy_addons.start()
    assert "DJANGO_SETTINGS_MODULE=settings.overlay" in text
    assert not re.search(r"^COPY\s+\S*config\.py\b", text, re.M)
    assert "/taiga-back/settings/config.py" not in text or "overlay.py" in text
    # never overwrite official config.py
    assert not re.search(r"COPY\s+\S+\s+/taiga-back/settings/config\.py", text)


def test_back_dockerfile_makes_stub_importable():
    text = _read(BACK_DF)
    assert "taiga_contrib_components" in text
    assert re.search(r"^COPY\s+addons/components/back", text, re.M) or "pip install" in text


def test_front_dockerfile_copies_plugin_and_later_hook():
    text = _read(FRONT_DF)
    assert re.search(r"plugins/components/", text)
    assert re.search(r"docker-entrypoint\.d/40", text)
    assert re.search(r"apk add(?: --no-cache)? jq", text)
    assert not re.search(r"COPY\s+\S+\s+/usr/share/nginx/html/conf\.json", text)
    assert not re.search(r"docker-entrypoint\.d/1[0-9]", text)
    assert not re.search(r"docker-entrypoint\.d/2[0-9]", text)
    assert not re.search(r"COPY\s+\S+\s+/docker-entrypoint\.d/30", text)


def test_front_patch_script_uses_jq_on_existing_conf():
    text = _read(PATCH_SH)
    assert "jq" in text
    assert "envsubst" not in text
    assert "contribPlugins" in text
    assert "unique" in text
    assert "conf.json" in text


def test_entrypoint_back_execs_official_script():
    text = _read(ENTRYPOINT_BACK)
    assert "exec" in text
    assert "/taiga-back/docker/entrypoint.sh" in text


def test_stub_app_importable_from_repo():
    sys.path.insert(0, str(STUB_BACK))
    try:
        sys.modules.pop("taiga_contrib_components", None)
        sys.modules.pop("taiga_contrib_components.apps", None)
        mod = importlib.import_module("taiga_contrib_components")
        assert mod is not None
        apps_src = _read(STUB_APP / "apps.py")
        assert 'name = "taiga_contrib_components"' in apps_src
        assert "models" not in apps_src.lower()
        assert "url" not in apps_src.lower()
    finally:
        if sys.path and sys.path[0] == str(STUB_BACK):
            sys.path.pop(0)
        sys.modules.pop("taiga_contrib_components", None)
        sys.modules.pop("taiga_contrib_components.apps", None)


def test_stub_plugin_files_exist_and_avoid_core_module_name():
    manifest = json.loads(_read(STUB_FRONT / "components.json"))
    assert manifest["slug"] == "components"
    assert manifest["module"] == "taigaContrib.components"
    assert manifest["js"] == "plugins/components/components.js"
    assert manifest["type"] not in {"admin", "auth", "userSettings"}
    js = _read(STUB_FRONT / "components.js")
    assert "taigaContrib.components" in js
    assert "taigaComponents" not in js


def _append_contrib_plugins(conf: dict, slugs: list[str]) -> dict:
    """Contract of patch-front-conf.sh (jq unique-append)."""
    overlay = _import_overlay()
    plugins = list(conf.get("contribPlugins") or [])
    for slug in slugs:
        path = overlay.contrib_plugin_path(slug)
        if path not in plugins:
            plugins.append(path)
    out = dict(conf)
    out["contribPlugins"] = plugins
    return out


def test_front_patch_fixture_keeps_urls_and_is_idempotent():
    fixture = {
        "api": "http://taiga.example/api/v1/",
        "eventsUrl": "ws://taiga.example/events",
        "baseHref": "/",
        "contribPlugins": ["plugins/slack/slack.json"],
    }
    once = _append_contrib_plugins(fixture, ["components"])
    twice = _append_contrib_plugins(once, ["components"])
    assert once["api"] == fixture["api"]
    assert once["eventsUrl"] == fixture["eventsUrl"]
    assert once["baseHref"] == fixture["baseHref"]
    assert once["contribPlugins"] == [
        "plugins/slack/slack.json",
        "plugins/components/components.json",
    ]
    assert twice["contribPlugins"] == once["contribPlugins"]


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_front_patch_script_mutates_fixture_conf(tmp_path):
    conf = tmp_path / "conf.json"
    addons = tmp_path / "addons.txt"
    conf.write_text(
        json.dumps(
            {
                "api": "http://taiga.example/api/v1/",
                "eventsUrl": "ws://taiga.example/events",
                "baseHref": "/",
                "contribPlugins": ["plugins/slack/slack.json"],
            }
        ),
        encoding="utf-8",
    )
    addons.write_text("# c\n\ncomponents\n", encoding="utf-8")
    env = os.environ.copy()
    env["TAIGA_FRONT_CONF"] = str(conf)
    env["TAIGA_ADDONS_TXT"] = str(addons)
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "POSIX shell required to run patch script"
    proc = subprocess.run(
        [shell, str(PATCH_SH)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(conf.read_text(encoding="utf-8"))
    assert data["api"] == "http://taiga.example/api/v1/"
    assert data["eventsUrl"] == "ws://taiga.example/events"
    assert data["baseHref"] == "/"
    assert data["contribPlugins"] == [
        "plugins/slack/slack.json",
        "plugins/components/components.json",
    ]
    proc2 = subprocess.run(
        [shell, str(PATCH_SH)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc2.returncode == 0, proc2.stderr
    again = json.loads(conf.read_text(encoding="utf-8"))
    assert again["contribPlugins"] == data["contribPlugins"]


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_live_overlay_images_load_stub_when_docker_present():
    """AC-3 live inspect. Skipped when Docker is absent — 1.3 owns smoke."""
    pin = (PLATFORM / "TAIGA_PIN").read_text(encoding="utf-8").strip()
    back_tag = f"taiga-addons-back:{pin}-story12"
    front_tag = f"taiga-addons-front:{pin}-story12"
    back_build = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(BACK_DF),
            "-t",
            back_tag,
            "--build-arg",
            f"TAIGA_PIN={pin}",
            str(REPO),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert back_build.returncode == 0, back_build.stderr
    front_build = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(FRONT_DF),
            "-t",
            front_tag,
            "--build-arg",
            f"TAIGA_PIN={pin}",
            str(REPO),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert front_build.returncode == 0, front_build.stderr
    try:
        imp = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "/opt/venv/bin/python",
                back_tag,
                "-c",
                "import taiga_contrib_components; print(taiga_contrib_components.__name__)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert imp.returncode == 0, imp.stderr
        assert "taiga_contrib_components" in imp.stdout

        ls = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "ls",
                front_tag,
                "/usr/share/nginx/html/plugins/components/components.json",
                "/usr/share/nginx/html/plugins/components/components.js",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert ls.returncode == 0, ls.stderr
    finally:
        subprocess.run(["docker", "rmi", "-f", back_tag, front_tag], capture_output=True)
