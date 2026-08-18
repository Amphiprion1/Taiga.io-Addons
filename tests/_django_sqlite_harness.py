"""Story 2.1 Layer B child process — Django + SQLite proof of AC-1/3/4/5.

Run as a script, never imported and never collected by pytest (the leading
underscore keeps it out of `test_*` discovery). `settings.configure()` and
`django.setup()` are irreversible per-process globals, so this body runs in its
own interpreter: the parent test asserts only on the exit code, and every global
this file mutates dies with the process.

argv[1] is the stub-app root (the parent's `tmp_path`), which must already
contain the generated `projects` and `userstories` apps. Both that root and the
addon's `back/` directory are expected on `PYTHONPATH`.

Exit 0 = every assertion held. Any other exit code = the traceback on stderr is
the failure the parent surfaces.
"""

from __future__ import annotations

import contextlib
import io
import sys

COMPONENT_TABLE = "taiga_contrib_components_component"
ASSIGNMENT_TABLE = "taiga_contrib_components_assignment"


@contextlib.contextmanager
def raises(exc):
    """Minimal `pytest.raises` — the child must not import pytest."""
    try:
        yield
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}, nothing was raised")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: _django_sqlite_harness.py <stub-root>")

    from django.conf import settings

    settings.configure(
        INSTALLED_APPS=[
            "projects",
            "userstories",
            "taiga_contrib_components",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        SECRET_KEY="story-2-1-harness",
        USE_TZ=True,
    )
    import django

    django.setup()

    from django.core.management import call_command
    from django.db import IntegrityError, connection, transaction
    from projects.models import Project
    from taiga_contrib_components.models import Assignment, Component
    from userstories.models import UserStory

    call_command("migrate", verbosity=0, run_syncdb=False)

    drift_out = io.StringIO()
    try:
        call_command(
            "makemigrations",
            "taiga_contrib_components",
            check=True,
            dry_run=True,
            verbosity=1,
            stdout=drift_out,
            stderr=drift_out,
        )
    except SystemExit as exc:
        raise AssertionError(
            f"makemigrations --check detected model/migration drift: {drift_out.getvalue()}"
        ) from exc

    tables = set(connection.introspection.table_names())
    assert COMPONENT_TABLE in tables
    assert ASSIGNMENT_TABLE in tables

    def columns(table: str) -> set[str]:
        with connection.cursor() as cursor:
            return {
                col.name
                for col in connection.introspection.get_table_description(cursor, table)
            }

    def table_ddl(table: str) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                [table],
            )
            row = cursor.fetchone()
            assert row is not None and row[0], table
            return row[0]

    component_cols = columns(COMPONENT_TABLE)
    assignment_cols = columns(ASSIGNMENT_TABLE)
    component_ddl = table_ddl(COMPONENT_TABLE)
    assignment_ddl = table_ddl(ASSIGNMENT_TABLE)
    assert "projects_project" not in component_ddl.lower()
    assert "userstories_userstory" not in assignment_ddl.lower()
    assert COMPONENT_TABLE in assignment_ddl
    assert {"id", "project_id", "name", "order"} <= component_cols
    assert "project_id_id" not in component_cols
    assert {"id", "userstory_id", "component_id"} <= assignment_cols
    assert "userstory_id_id" not in assignment_cols
    assert "component_id_id" not in assignment_cols

    project_a = Project.objects.create(name="A")
    project_b = Project.objects.create(name="B")
    story = UserStory.objects.create(subject="US")

    api = Component.objects.create(project=project_a, name="API")
    with raises(IntegrityError):
        with transaction.atomic():
            Component.objects.create(project=project_a, name="api")

    other = Component.objects.create(project=project_b, name="API")
    assert other.name == "API"

    padded = Component(project=project_b, name="  Front  ")
    padded.save()
    padded.refresh_from_db()
    assert padded.name == "Front"
    with raises(IntegrityError):
        with transaction.atomic():
            Component.objects.create(project=project_b, name="  FRONT  ")

    Assignment.objects.create(userstory=story, component=api)
    with raises(IntegrityError):
        with transaction.atomic():
            Assignment.objects.create(userstory=story, component=api)

    doomed = Component.objects.create(project=project_a, name="Doomed")
    Assignment.objects.create(userstory=story, component=doomed)
    doomed_id = doomed.id
    story_id = story.id
    doomed.delete()
    assert not Assignment.objects.filter(component_id=doomed_id).exists()
    assert UserStory.objects.filter(pk=story_id).exists()

    call_command("migrate", "taiga_contrib_components", "zero", verbosity=0)
    tables_after = set(connection.introspection.table_names())
    assert COMPONENT_TABLE not in tables_after
    assert ASSIGNMENT_TABLE not in tables_after


if __name__ == "__main__":
    main()
