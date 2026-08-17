"""Overlay Django settings: official env-driven config plus addon apps."""

from __future__ import annotations

import os
from pathlib import Path

ADDONS_TXT_DEFAULT = "/opt/taiga-addons/addons.txt"


def parse_addon_slugs(text: str) -> list[str]:
    slugs: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            slugs.append(line)
    return slugs


def contrib_app_label(slug: str) -> str:
    return f"taiga_contrib_{slug}"


def contrib_plugin_path(slug: str) -> str:
    return f"plugins/{slug}/{slug}.json"


def append_contrib_apps(installed_apps, slugs):
    apps = list(installed_apps)
    for slug in slugs:
        label = contrib_app_label(slug)
        if label not in apps:
            apps.append(label)
    return apps


def load_addon_slugs(path: str | Path | None = None) -> list[str]:
    addons_path = Path(
        path
        if path is not None
        else os.environ.get("TAIGA_ADDONS_TXT", ADDONS_TXT_DEFAULT)
    )
    return parse_addon_slugs(addons_path.read_text(encoding="utf-8"))


def apply_overlay(installed_apps, path: str | Path | None = None):
    return append_contrib_apps(installed_apps, load_addon_slugs(path))


# Official env-driven settings stay. Append only after this import.
# Django loads this module as settings.overlay; repo tests import it as overlay.
if __name__ == "settings.overlay":
    from .config import *  # noqa: E402, F403

    INSTALLED_APPS = apply_overlay(INSTALLED_APPS)  # noqa: F405
