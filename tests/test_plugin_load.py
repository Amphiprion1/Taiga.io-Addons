"""Story 1.2 — append Addon apps/plugins without replacing official config."""

from __future__ import annotations

import ast
import contextlib
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
INSTALL_SH = PLATFORM / "install-enabled-addons.sh"
GITATTRIBUTES = REPO / ".gitattributes"
STUB_BACK = REPO / "addons" / "components" / "back"
STUB_APP = STUB_BACK / "taiga_contrib_components"
STUB_FRONT = REPO / "addons" / "components" / "front"

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
from _addon_package import ALLOWED_STUB_APP_ENTRIES  # noqa: E402
APPS_READY_IMPORTS = {
    ("django.urls", 0),
    ("taiga.base", 0),
    ("taiga.urls", 0),
    ("api", 1),
}

_GIT_SHELLS = (
    r"C:\Program Files\Git\bin\sh.exe",
    r"C:\Program Files\Git\usr\bin\sh.exe",
    r"C:\Program Files\Git\bin\bash.exe",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _posix_shell() -> str | None:
    # Prefer Git's sh. WindowsApps\bash.exe is a Store stub, not a shell.
    candidates = [*_GIT_SHELLS, shutil.which("sh"), shutil.which("bash")]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file() and "WindowsApps" not in str(path):
            return str(path)
    return None


def _import_overlay():
    sys.path.insert(0, str(PLATFORM))
    try:
        sys.modules.pop("overlay", None)
        return importlib.import_module("overlay")
    finally:
        if sys.path and sys.path[0] == str(PLATFORM):
            sys.path.pop(0)


@contextlib.contextmanager
def _swap_settings_modules():
    saved = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name == "settings" or name.startswith("settings.")
    }
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == "settings" or name.startswith("settings."):
                del sys.modules[name]
        sys.modules.update(saved)


def test_addons_txt_parser_maps_components_and_ignores_noise():
    overlay = _import_overlay()
    text = _read(ADDONS_TXT)
    slugs = overlay.parse_addon_slugs(text)
    assert slugs == ["components"]
    assert overlay.contrib_app_label("components") == "taiga_contrib_components"
    assert overlay.contrib_plugin_path("components") == "plugins/components/components.json"

    noisy = "# enabled slugs\n\ncomponents  # tail comment\n# ignored\n  \n"
    assert overlay.parse_addon_slugs(noisy) == ["components"]
    assert overlay.parse_addon_slugs("components\r\n") == ["components"]


def test_parse_addon_slugs_rejects_unsafe_values():
    overlay = _import_overlay()
    for bad in ("../etc", "Slack", "foo-bar", "foo.bar", "components;rm", "1abc"):
        with pytest.raises(ValueError, match="invalid addon slug"):
            overlay.parse_addon_slugs(bad)


def test_missing_addons_txt_explains_path(tmp_path):
    overlay = _import_overlay()
    missing = tmp_path / "nope-addons.txt"
    with pytest.raises(FileNotFoundError) as exc:
        overlay.load_addon_slugs(missing)
    msg = str(exc.value)
    assert "nope-addons.txt" in msg
    assert "addon registry" in msg.lower()


def test_overlay_source_imports_official_config_before_append():
    text = _read(OVERLAY_PY)
    import_idx = text.find("from .config import *")
    if import_idx < 0:
        import_idx = text.find("from settings.config import *")
    append_idx = text.find("INSTALLED_APPS = apply_overlay")
    assert import_idx >= 0, "overlay must star-import official config"
    assert 0 <= import_idx < append_idx
    assert '__name__ == "settings.overlay"' not in text


def test_overlay_fails_closed_when_loaded_without_official_config(tmp_path, monkeypatch):
    dest = tmp_path / "misnamed.py"
    dest.write_text(_read(OVERLAY_PY), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("misnamed", None)
    try:
        with pytest.raises(ImportError, match="settings.config|official"):
            importlib.import_module("misnamed")
    finally:
        sys.modules.pop("misnamed", None)


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
    with _swap_settings_modules():
        loaded = importlib.import_module("settings.overlay")
        assert loaded.TAIGA_SITES_DOMAIN == "example.test"
        assert loaded.SECRET_KEY == "official-secret"
        assert loaded.INSTALLED_APPS == [
            "django.contrib.admin",
            "taiga.base",
            "taiga_contrib_components",
        ]
        assert overlay.append_contrib_apps(loaded.INSTALLED_APPS, ["components"]) == list(
            loaded.INSTALLED_APPS
        )


def test_back_dockerfile_copies_addons_and_bakes_overlay_settings():
    text = _read(BACK_DF)
    parts = re.split(r"^FROM .+$", text, maxsplit=1, flags=re.M)
    assert len(parts) == 2
    after = parts[1]
    arg_m = re.search(r"^ARG TAIGA_PIN\b", after, re.M)
    copy_addons = re.search(
        r"^COPY\s+\S*addons\.txt\s+/opt/taiga-addons/addons\.txt", after, re.M
    )
    copy_tree = re.search(r"^COPY\s+addons\s+/opt/taiga-addons/src\s*$", after, re.M)
    copy_overlay = re.search(
        r"^COPY\s+\S*overlay\.py\s+/taiga-back/settings/overlay\.py", after, re.M
    )
    assert arg_m, "post-FROM ARG TAIGA_PIN required"
    assert copy_addons, "must COPY addons.txt after FROM"
    assert copy_tree, "must COPY the whole addons/ tree (AD-9)"
    assert copy_overlay, "must COPY overlay.py into official settings/"
    assert arg_m.start() < copy_addons.start()
    assert "DJANGO_SETTINGS_MODULE=settings.overlay" in text
    assert not re.search(r"^COPY\s+\S*config\.py\b", text, re.M)
    assert not re.search(r"COPY\s+\S+\s+/taiga-back/settings/config\.py", text)
    assert "entrypoint-back.sh" not in text


def test_dockerfiles_fan_out_enabled_slugs_from_registry():
    install = _read(INSTALL_SH)
    assert "addons.txt" in install
    assert "taiga_contrib_" in install
    assert "FRONT_DEST" in install or "/usr/share/nginx/html/plugins" in install
    for path in (BACK_DF, FRONT_DF):
        text = _read(path)
        assert re.search(r"^COPY\s+addons\s+/opt/taiga-addons/src\s*$", text, re.M), path.name
        assert "install-enabled-addons.sh" in text
        assert not re.search(r"^COPY\s+addons/components/", text, re.M), path.name


def test_front_dockerfile_copies_plugin_and_later_hook():
    text = _read(FRONT_DF)
    assert re.search(r"docker-entrypoint\.d/40", text)
    assert re.search(r"apk add(?: --no-cache)? jq", text)
    assert "install-enabled-addons.sh" in text
    assert not re.search(r"COPY\s+\S+\s+/usr/share/nginx/html/conf\.json", text)
    assert not re.search(r"docker-entrypoint\.d/1[0-9]", text)
    assert not re.search(r"docker-entrypoint\.d/2[0-9]", text)
    assert not re.search(r"COPY\s+\S+\s+/docker-entrypoint\.d/30", text)


def test_front_patch_script_uses_jq_on_existing_conf():
    text = _read(PATCH_SH)
    assert "jq" in text
    assert "envsubst" not in text
    assert "contribPlugins" in text
    assert "conf.json" in text
    assert not re.search(r"\|\s*unique\b", text), "jq unique sorts official plugins"
    assert "index($x) != null" in text
    assert re.search(r"cat\s+\"\$tmp\"\s*>\s*\"\$CONF\"", text)
    assert not re.search(r"\bmv\s+\"\$tmp\"\s+\"\$CONF\"", text)


def test_gitattributes_forces_lf_for_shell_scripts():
    text = _read(GITATTRIBUTES)
    assert "*.sh" in text
    assert "eol=lf" in text


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
        tree = ast.parse(apps_src)
        top_imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                top_imports.append(node.module)
            elif isinstance(node, ast.Import):
                top_imports.extend(alias.name for alias in node.names)
        assert top_imports == ["django.apps"]
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1
        assert classes[0].name == "ComponentsConfig"
        assigns = {}
        ready_fn = None
        for node in classes[0].body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                assigns[node.targets[0].id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.FunctionDef) and node.name == "ready":
                ready_fn = node
        assert assigns["name"] == "taiga_contrib_components"
        assert ready_fn is not None
        ready_imports = set()
        for node in ast.walk(ready_fn):
            if isinstance(node, ast.ImportFrom) and node.module:
                ready_imports.add((node.module, node.level))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    ready_imports.add((alias.name, 0))
        assert ready_imports == APPS_READY_IMPORTS
        entries = {p.name for p in STUB_APP.iterdir() if p.name != "__pycache__"}
        assert entries == ALLOWED_STUB_APP_ENTRIES
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


def _write_addon_tree(root: Path, slug: str) -> None:
    back = root / slug / "back" / f"taiga_contrib_{slug}"
    front = root / slug / "front"
    back.mkdir(parents=True)
    front.mkdir(parents=True)
    (back / "__init__.py").write_text(f"# {slug}\n", encoding="utf-8")
    (front / f"{slug}.json").write_text("{}", encoding="utf-8")
    (front / f"{slug}.js").write_text(";\n", encoding="utf-8")


def _run_sh(args: list[str], env: dict[str, str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    shell = _posix_shell()
    assert shell, "POSIX shell required"
    merged = os.environ.copy()
    merged.update(env)
    merged.setdefault("MSYS_NO_PATHCONV", "1")
    return subprocess.run(
        [shell, *args],
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.skipif(_posix_shell() is None, reason="POSIX shell not installed")
def test_install_script_fans_out_only_enabled_slugs(tmp_path):
    src = tmp_path / "src"
    addons = tmp_path / "addons.txt"
    back_dest = tmp_path / "taiga-back"
    front_dest = tmp_path / "plugins"
    back_dest.mkdir()
    front_dest.mkdir()
    _write_addon_tree(src, "components")
    _write_addon_tree(src, "other")
    addons.write_text("# enabled\ncomponents\n", encoding="utf-8")
    env = {
        "TAIGA_ADDONS_TXT": str(addons),
        "TAIGA_ADDONS_SRC": str(src),
        "TAIGA_BACK_DEST": str(back_dest),
        "TAIGA_FRONT_DEST": str(front_dest),
    }
    back = _run_sh([str(INSTALL_SH), "back"], env)
    assert back.returncode == 0, f"{back.stdout or ''}{back.stderr or ''}"
    assert (back_dest / "taiga_contrib_components" / "__init__.py").is_file()
    assert not (back_dest / "taiga_contrib_other").exists()
    front = _run_sh([str(INSTALL_SH), "front"], env)
    assert front.returncode == 0, f"{front.stdout or ''}{front.stderr or ''}"
    assert (front_dest / "components" / "components.json").is_file()
    assert not (front_dest / "other").exists()


@pytest.mark.skipif(_posix_shell() is None, reason="POSIX shell not installed")
def test_install_script_rejects_invalid_slug(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    addons = tmp_path / "addons.txt"
    addons.write_text("../etc\n", encoding="utf-8")
    proc = _run_sh(
        [str(INSTALL_SH), "back"],
        {
            "TAIGA_ADDONS_TXT": str(addons),
            "TAIGA_ADDONS_SRC": str(src),
            "TAIGA_BACK_DEST": str(tmp_path / "dest"),
        },
    )
    assert proc.returncode != 0
    assert "invalid slug" in f"{proc.stdout or ''}{proc.stderr or ''}".lower()


@pytest.mark.skipif(_posix_shell() is None, reason="POSIX shell not installed")
def test_front_patch_script_rejects_invalid_slug(tmp_path):
    conf = tmp_path / "conf.json"
    addons = tmp_path / "addons.txt"
    conf.write_text('{"contribPlugins":[]}', encoding="utf-8")
    addons.write_text("foo-bar\n", encoding="utf-8")
    proc = _run_sh(
        [str(PATCH_SH)],
        {"TAIGA_FRONT_CONF": str(conf), "TAIGA_ADDONS_TXT": str(addons)},
    )
    assert proc.returncode != 0
    assert "invalid slug" in f"{proc.stdout or ''}{proc.stderr or ''}".lower()


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_front_patch_script_mutates_fixture_conf(tmp_path):
    """Runs the shipped script. Skipped without jq — not a Python reimplementation."""
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
    shell = _posix_shell()
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
