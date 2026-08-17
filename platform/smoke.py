"""Fail-closed overlay smoke: stub Addon is in INSTALLED_APPS and contribPlugins."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_PLATFORM = Path(__file__).resolve().parent
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))

import overlay  # noqa: E402

SUBPROCESS_TIMEOUT = 60
EXIT_CHECK = 1
EXIT_ENV = 2
EXIT_EXEC = 3


class SmokeError(Exception):
    """One or more overlay smoke checks failed."""


def resolve_addons_file(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    root = os.environ.get("TAIGA_ADDONS_ROOT")
    if root:
        return Path(root) / "platform" / "addons.txt"
    return _PLATFORM / "addons.txt"


def resolve_compose_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("TAIGA_DOCKER")
    if env:
        return Path(env)
    return Path.cwd()


def load_slugs(addons_file: Path) -> list[str]:
    return overlay.parse_addon_slugs(addons_file.read_text(encoding="utf-8"))


def check_installed_apps(apps: list[str], slugs: list[str]) -> None:
    missing = [
        overlay.contrib_app_label(slug)
        for slug in slugs
        if overlay.contrib_app_label(slug) not in apps
    ]
    if missing:
        raise SmokeError("missing INSTALLED_APPS: " + ", ".join(missing))


def check_contrib_plugins(conf: dict, slugs: list[str]) -> None:
    plugins = conf.get("contribPlugins")
    if not isinstance(plugins, list):
        raise SmokeError("contribPlugins is not a list (corrupted conf.json)")
    missing = [
        overlay.contrib_plugin_path(slug)
        for slug in slugs
        if overlay.contrib_plugin_path(slug) not in plugins
    ]
    if missing:
        raise SmokeError("missing contribPlugins: " + ", ".join(missing))


def _collect(apps: list[str], conf: dict, slugs: list[str]) -> list[str]:
    errors: list[str] = []
    try:
        check_installed_apps(apps, slugs)
    except SmokeError as exc:
        errors.append(str(exc))
    try:
        check_contrib_plugins(conf, slugs)
    except SmokeError as exc:
        errors.append(str(exc))
    return errors


def _fail(errors: list[str]) -> int:
    print("\n".join(errors), file=sys.stderr)
    return EXIT_CHECK


def _run_offline(apps_file: Path, conf_file: Path, slugs: list[str]) -> int:
    try:
        apps = json.loads(apps_file.read_text(encoding="utf-8"))
        conf = json.loads(conf_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"overlay smoke: cannot read fixture: {exc}", file=sys.stderr)
        return EXIT_CHECK
    if not isinstance(apps, list) or not isinstance(conf, dict):
        print(
            "overlay smoke: --apps-file must be a JSON list and --conf-file a JSON object",
            file=sys.stderr,
        )
        return EXIT_CHECK
    errors = _collect(apps, conf, slugs)
    return _fail(errors) if errors else 0


def _compose_exec(
    service_and_cmd: list[str], compose_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *service_and_cmd],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(compose_dir),
        timeout=SUBPROCESS_TIMEOUT,
    )


def _compose_file_present(compose_dir: Path) -> bool:
    return (compose_dir / "docker-compose.yml").is_file() or (
        compose_dir / "compose.yml"
    ).is_file()


def _looks_like_missing_compose(proc: subprocess.CompletedProcess[str]) -> bool:
    blob = f"{proc.stderr or ''}{proc.stdout or ''}".lower()
    return (
        "is not a docker command" in blob
        or "unknown command" in blob
        or "no configuration file" in blob
        or "compose is not installed" in blob
    )


def _run_live(slugs: list[str], compose_dir: Path) -> int:
    if shutil.which("docker") is None:
        print("no running overlay: docker is not installed", file=sys.stderr)
        return EXIT_ENV

    if not _compose_file_present(compose_dir):
        print(
            "no running overlay: no docker-compose.yml in "
            f"{compose_dir} (run from official taiga-docker/ or pass "
            "--compose-dir / set TAIGA_DOCKER)",
            file=sys.stderr,
        )
        return EXIT_ENV

    try:
        back = _compose_exec(
            [
                "taiga-back",
                "/opt/venv/bin/python",
                "-c",
                "from django.conf import settings; import json; "
                "print(json.dumps(list(settings.INSTALLED_APPS)))",
            ],
            compose_dir,
        )
    except subprocess.TimeoutExpired:
        print("overlay exec failed: taiga-back timed out", file=sys.stderr)
        return EXIT_EXEC

    if back.returncode != 0:
        detail = (back.stderr or back.stdout or "").strip()
        if _looks_like_missing_compose(back):
            print(
                "no running overlay: docker compose v2 is required "
                f"in {compose_dir}",
                file=sys.stderr,
            )
            if detail:
                print(detail, file=sys.stderr)
            return EXIT_ENV
        print("overlay exec failed: docker compose exec taiga-back", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        return EXIT_EXEC

    try:
        front = _compose_exec(
            ["taiga-front", "cat", "/usr/share/nginx/html/conf.json"],
            compose_dir,
        )
    except subprocess.TimeoutExpired:
        print("overlay exec failed: taiga-front timed out", file=sys.stderr)
        return EXIT_EXEC

    if front.returncode != 0:
        detail = (front.stderr or front.stdout or "").strip()
        if _looks_like_missing_compose(front):
            print(
                "no running overlay: docker compose v2 is required "
                f"in {compose_dir}",
                file=sys.stderr,
            )
            if detail:
                print(detail, file=sys.stderr)
            return EXIT_ENV
        print("overlay exec failed: docker compose exec taiga-front", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        return EXIT_EXEC

    try:
        apps = json.loads(back.stdout)
        conf = json.loads(front.stdout)
    except json.JSONDecodeError as exc:
        print(f"overlay smoke: invalid JSON from container: {exc}", file=sys.stderr)
        return EXIT_CHECK
    if not isinstance(apps, list) or not isinstance(conf, dict):
        print("overlay smoke: unexpected payload from containers", file=sys.stderr)
        return EXIT_CHECK

    errors = _collect(apps, conf, slugs)
    return _fail(errors) if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed smoke: stub Addon loaded in back apps and front plugins."
    )
    parser.add_argument("--apps-file", type=Path, help="JSON list of INSTALLED_APPS (offline)")
    parser.add_argument("--conf-file", type=Path, help="front conf.json object (offline)")
    parser.add_argument("--addons-file", help="addons.txt (default: repo/env, never host /opt)")
    parser.add_argument(
        "--compose-dir",
        help="official taiga-docker compose project (default: $TAIGA_DOCKER or cwd)",
    )
    args = parser.parse_args(argv)

    if (args.apps_file is None) ^ (args.conf_file is None):
        print(
            "overlay smoke: pass both --apps-file and --conf-file, or neither for live mode",
            file=sys.stderr,
        )
        return EXIT_CHECK

    addons_file = resolve_addons_file(args.addons_file)
    try:
        slugs = load_slugs(addons_file)
    except (OSError, ValueError) as exc:
        print(f"overlay smoke: cannot read addons: {exc}", file=sys.stderr)
        return EXIT_CHECK

    if not slugs:
        print(
            "overlay smoke: no enabled addons in addons.txt (fail-closed)",
            file=sys.stderr,
        )
        return EXIT_CHECK

    if args.apps_file is not None and args.conf_file is not None:
        return _run_offline(args.apps_file, args.conf_file, slugs)
    return _run_live(slugs, resolve_compose_dir(args.compose_dir))


if __name__ == "__main__":
    raise SystemExit(main())
