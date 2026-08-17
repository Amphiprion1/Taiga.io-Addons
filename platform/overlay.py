"""Overlay Django settings: official env-driven config plus addon apps."""

from __future__ import annotations

import os
import re
from pathlib import Path

ADDONS_TXT_DEFAULT = "/opt/taiga-addons/addons.txt"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def parse_addon_slugs(text: str) -> list[str]:
    slugs: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].replace("\r", "").strip()
        if not line:
            continue
        if not SLUG_RE.fullmatch(line):
            raise ValueError(f"invalid addon slug: {line!r}")
        if line not in slugs:
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
    try:
        text = addons_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"addon registry missing: {addons_path}. "
            "Image build must COPY platform/addons.txt to /opt/taiga-addons/addons.txt."
        ) from exc
    return parse_addon_slugs(text)


def apply_overlay(installed_apps, path: str | Path | None = None):
    return append_contrib_apps(installed_apps, load_addon_slugs(path))


# Helper imports (`import overlay` from platform/) must not require official config.
# Any other module name is treated as Django settings: import official config or
# fail loudly. Silent skip would leave INSTALLED_APPS without addon apps.
_HELPER_IMPORT = __name__ == "overlay" and __package__ in {None, ""}

if not _HELPER_IMPORT:
    try:
        from .config import *  # noqa: E402, F403
    except ImportError as exc:
        raise ImportError(
            "settings.overlay requires official settings.config next to this module; "
            f"loaded as {__name__!r}."
        ) from exc

    INSTALLED_APPS = apply_overlay(INSTALLED_APPS)  # noqa: F405
