"""Story 1.1 — overlay scaffolding invariants (no live Taiga stack)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
PLATFORM = REPO / "platform"
PIN_FILE = PLATFORM / "TAIGA_PIN"
BACK_DF = PLATFORM / "back.Dockerfile"
FRONT_DF = PLATFORM / "front.Dockerfile"
OVERRIDE = PLATFORM / "docker-compose.override.yml"
README = PLATFORM / "README.md"
ENV_EXAMPLE = PLATFORM / "compose.env.example"
DOCKERIGNORE = REPO / ".dockerignore"
DEV_REQUIREMENTS = REPO / "requirements-dev.txt"

PIN_DEFAULT_RE = re.compile(r"\$\{TAIGA_PIN:-([^}]+)\}")
OFFICIAL_ONLY_SERVICES = {
    "taiga-db",
    "taiga-events",
    "taiga-protected",
    "taiga-gateway",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _declared_pin() -> str:
    pin = _read(PIN_FILE).strip()
    assert pin, "platform/TAIGA_PIN must declare a tag"
    assert pin != "latest"
    assert ":" not in pin
    assert "\n" not in pin
    return pin


def test_taiga_pin_is_single_declared_seed():
    assert PIN_FILE.is_file(), "platform/TAIGA_PIN must exist"
    pin = _declared_pin()
    assert pin in _read(README)


def test_back_dockerfile_from_pinned_official_image():
    pin = _declared_pin()
    text = _read(BACK_DF)
    assert f"ARG TAIGA_PIN={pin}" in text or f'ARG TAIGA_PIN="{pin}"' in text
    assert re.search(r"^FROM taigaio/taiga-back:\$\{TAIGA_PIN\}", text, re.M)
    assert ":latest" not in text


def test_front_dockerfile_from_pinned_official_image():
    pin = _declared_pin()
    text = _read(FRONT_DF)
    assert f"ARG TAIGA_PIN={pin}" in text or f'ARG TAIGA_PIN="{pin}"' in text
    assert re.search(r"^FROM taigaio/taiga-front:\$\{TAIGA_PIN\}", text, re.M)
    assert ":latest" not in text


def test_dockerfiles_share_pin_file_value():
    pin = _declared_pin()
    for path in (BACK_DF, FRONT_DF):
        text = _read(path)
        assert f"ARG TAIGA_PIN={pin}" in text or f'ARG TAIGA_PIN="{pin}"' in text


def test_dockerfiles_redeclare_arg_after_from():
    for path in (BACK_DF, FRONT_DF):
        text = _read(path)
        parts = re.split(r"^FROM .+$", text, maxsplit=1, flags=re.M)
        assert len(parts) == 2, f"{path.name} must have a FROM line"
        assert re.search(r"^ARG TAIGA_PIN\b", parts[1], re.M), (
            f"{path.name} must redeclare ARG TAIGA_PIN after FROM"
        )


def _load_override():
    data = yaml.safe_load(_read(OVERRIDE))
    assert isinstance(data, dict)
    return data


def test_override_defaults_match_pin_file():
    pin = _declared_pin()
    defaults = PIN_DEFAULT_RE.findall(_read(OVERRIDE))
    assert defaults, "override must provide ${TAIGA_PIN:-<pin>} defaults"
    assert set(defaults) == {pin}


def test_override_only_swaps_back_async_front():
    data = _load_override()
    services = data["services"]
    assert set(services) == {"taiga-back", "taiga-async", "taiga-front"}


def test_override_omits_official_only_services():
    """Override must not declare official-only services; compose leaves them as-is."""
    services = set(_load_override()["services"])
    assert services.isdisjoint(OFFICIAL_ONLY_SERVICES)


def test_override_back_and_async_use_same_image():
    services = _load_override()["services"]
    assert services["taiga-back"]["image"] == services["taiga-async"]["image"]
    image = services["taiga-back"]["image"]
    assert image.startswith("taiga-addons-back:")
    assert "TAIGA_PIN" in image
    assert ":latest" not in image


def test_override_front_uses_distinct_overlay_image():
    services = _load_override()["services"]
    front = services["taiga-front"]["image"]
    assert front.startswith("taiga-addons-front:")
    assert "TAIGA_PIN" in front
    assert front != services["taiga-back"]["image"]


def test_override_build_context_is_addons_root():
    services = _load_override()["services"]
    expected = {
        "taiga-back": "platform/back.Dockerfile",
        "taiga-front": "platform/front.Dockerfile",
    }
    for name, dockerfile in expected.items():
        build = services[name]["build"]
        assert "TAIGA_ADDONS_ROOT" in build["context"]
        assert build["dockerfile"].replace("\\", "/") == dockerfile
        assert "TAIGA_PIN" in str(build.get("args", {}))
    assert "build" not in services["taiga-async"]


def test_override_does_not_pull_local_overlay_images():
    services = _load_override()["services"]
    for name in ("taiga-back", "taiga-async", "taiga-front"):
        assert services[name].get("pull_policy") == "never", name


def test_override_does_not_replace_official_config_files():
    text = _read(OVERRIDE)
    assert "config.py" not in text
    assert "conf.json" not in text
    assert "INSTALLED_APPS" not in text
    assert "contribPlugins" not in text


def test_override_does_not_touch_async_entrypoint():
    async_svc = _load_override()["services"]["taiga-async"]
    assert "entrypoint" not in async_svc
    assert "command" not in async_svc


def test_override_compose_version_compatible():
    data = _load_override()
    if "version" in data:
        assert str(data["version"]) in {"3.5", "3.8", "3.9"}


def test_addon_tree_placeholders_exist():
    assert (REPO / "addons" / "components" / "back" / ".gitkeep").is_file()
    assert (REPO / "addons" / "components" / "front" / ".gitkeep").is_file()


def test_readme_documents_attach_and_pin():
    pin = _declared_pin()
    text = _read(README)
    for needle in (
        "TAIGA_ADDONS_ROOT",
        "TAIGA_PIN",
        "docker-compose.override.yml",
        "docker compose",
        pin,
        ".env",
        "docker compose down",
        "-f docker-compose.yml -f docker-compose.override.yml config",
        "docker compose pull",
    ):
        assert needle in text, f"README missing {needle!r}"


def test_env_example_matches_pin_file():
    pin = _declared_pin()
    text = _read(ENV_EXAMPLE)
    assert "TAIGA_ADDONS_ROOT=" in text
    assert f"TAIGA_PIN={pin}" in text


def test_dockerignore_excludes_non_image_paths():
    text = _read(DOCKERIGNORE)
    for needle in ("_bmad", "docs", ".agents", ".pytest_cache"):
        assert needle in text, f".dockerignore missing {needle!r}"


def test_dev_requirements_declare_test_deps():
    text = _read(DEV_REQUIREMENTS).lower()
    assert "pytest" in text
    assert "yaml" in text or "pyyaml" in text


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_docker_compose_config_merges_when_docker_present(tmp_path):
    pin = _declared_pin()
    official = tmp_path / "docker-compose.yml"
    official.write_text(
        yaml.safe_dump(
            {
                "version": "3.5",
                "services": {
                    "taiga-db": {"image": "postgres:12.3"},
                    "taiga-back": {"image": "taigaio/taiga-back:latest"},
                    "taiga-async": {
                        "image": "taigaio/taiga-back:latest",
                        "entrypoint": ["/taiga-back/docker/async_entrypoint.sh"],
                    },
                    "taiga-front": {"image": "taigaio/taiga-front:latest"},
                    "taiga-gateway": {"image": "nginx:1.19-alpine"},
                },
            }
        ),
        encoding="utf-8",
    )
    override_copy = tmp_path / "docker-compose.override.yml"
    override_copy.write_text(_read(OVERRIDE), encoding="utf-8")
    env = os.environ.copy()
    env["TAIGA_ADDONS_ROOT"] = str(REPO)
    env["TAIGA_PIN"] = pin
    proc = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(official),
            "-f",
            str(override_copy),
            "config",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rendered = yaml.safe_load(proc.stdout)
    images = {name: svc["image"] for name, svc in rendered["services"].items()}
    assert images["taiga-back"] == images["taiga-async"]
    assert "taiga-addons-back" in images["taiga-back"]
    assert "taiga-addons-front" in images["taiga-front"]
    assert pin in images["taiga-back"]
    assert images["taiga-gateway"].startswith("nginx")
