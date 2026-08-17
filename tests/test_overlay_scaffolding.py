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
SEED_PIN = "6.10.2"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_taiga_pin_is_single_declared_seed():
    assert PIN_FILE.is_file(), "platform/TAIGA_PIN must exist"
    pin = PIN_FILE.read_text(encoding="utf-8").strip()
    assert pin == SEED_PIN
    assert "\n" not in PIN_FILE.read_text(encoding="utf-8").strip()


def test_back_dockerfile_from_pinned_official_image():
    text = _read(BACK_DF)
    assert re.search(r"^ARG TAIGA_PIN=", text, re.M)
    assert f"ARG TAIGA_PIN={SEED_PIN}" in text or f'ARG TAIGA_PIN="{SEED_PIN}"' in text
    assert re.search(r"^FROM taigaio/taiga-back:\$\{TAIGA_PIN\}", text, re.M)
    assert ":latest" not in text


def test_front_dockerfile_from_pinned_official_image():
    text = _read(FRONT_DF)
    assert re.search(r"^ARG TAIGA_PIN=", text, re.M)
    assert f"ARG TAIGA_PIN={SEED_PIN}" in text or f'ARG TAIGA_PIN="{SEED_PIN}"' in text
    assert re.search(r"^FROM taigaio/taiga-front:\$\{TAIGA_PIN\}", text, re.M)
    assert ":latest" not in text


def test_dockerfiles_share_pin_file_value():
    pin = PIN_FILE.read_text(encoding="utf-8").strip()
    for path in (BACK_DF, FRONT_DF):
        text = _read(path)
        assert f"ARG TAIGA_PIN={pin}" in text or f'ARG TAIGA_PIN="{pin}"' in text


def _load_override():
    data = yaml.safe_load(_read(OVERRIDE))
    assert isinstance(data, dict)
    return data


def test_override_only_swaps_back_async_front():
    data = _load_override()
    services = data["services"]
    assert set(services) == {"taiga-back", "taiga-async", "taiga-front"}


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
    for name in ("taiga-back", "taiga-front"):
        build = services[name]["build"]
        assert "TAIGA_ADDONS_ROOT" in build["context"]
        assert build["dockerfile"].replace("\\", "/") in {
            "platform/back.Dockerfile" if name == "taiga-back" else "platform/front.Dockerfile"
        }
        assert "TAIGA_PIN" in str(build.get("args", {}))
    assert "build" not in services["taiga-async"]


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
    text = _read(README)
    for needle in (
        "TAIGA_ADDONS_ROOT",
        "TAIGA_PIN",
        "docker-compose.override.yml",
        "docker compose",
        "6.10.2",
    ):
        assert needle in text, f"README missing {needle!r}"


def test_static_merge_keeps_official_services():
    """Simulate compose merge: override must not drop gateway/db/events."""
    official = {
        "version": "3.5",
        "services": {
            "taiga-db": {"image": "postgres:12.3"},
            "taiga-back": {"image": "taigaio/taiga-back:latest"},
            "taiga-async": {
                "image": "taigaio/taiga-back:latest",
                "entrypoint": ["/taiga-back/docker/async_entrypoint.sh"],
            },
            "taiga-front": {"image": "taigaio/taiga-front:latest"},
            "taiga-events": {"image": "taigaio/taiga-events:latest"},
            "taiga-protected": {"image": "taigaio/taiga-protected:latest"},
            "taiga-gateway": {"image": "nginx:1.19-alpine"},
        },
    }
    override = _load_override()
    merged = {**official["services"]}
    for name, spec in override["services"].items():
        merged[name] = {**merged.get(name, {}), **spec}

    assert set(official["services"]) <= set(merged)
    assert merged["taiga-gateway"]["image"] == "nginx:1.19-alpine"
    assert merged["taiga-db"]["image"] == "postgres:12.3"
    assert merged["taiga-events"]["image"] == "taigaio/taiga-events:latest"
    assert merged["taiga-async"]["entrypoint"] == ["/taiga-back/docker/async_entrypoint.sh"]
    assert merged["taiga-back"]["image"] == merged["taiga-async"]["image"]
    assert merged["taiga-back"]["image"].startswith("taiga-addons-back:")
    assert merged["taiga-front"]["image"].startswith("taiga-addons-front:")


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_docker_compose_config_merges_when_docker_present(tmp_path):
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
    env["TAIGA_PIN"] = SEED_PIN
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
    assert "6.10.2" in images["taiga-back"]
    assert images["taiga-gateway"].startswith("nginx")
