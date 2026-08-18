"""Story 2.1 — Component/Assignment models and addon-owned migrations."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STUB_BACK = REPO / "addons" / "components" / "back"
STUB_APP = STUB_BACK / "taiga_contrib_components"
MODELS_PY = STUB_APP / "models.py"
APPS_PY = STUB_APP / "apps.py"
INIT_PY = STUB_APP / "__init__.py"
MIGRATIONS = STUB_APP / "migrations"
MIGRATION_INIT = MIGRATIONS / "__init__.py"
MIGRATION_0001 = MIGRATIONS / "0001_initial.py"
HARNESS_CHILD = Path(__file__).resolve().parent / "_django_sqlite_harness.py"
TAIGA_STUB = Path(__file__).resolve().parent / "_taiga_stub"
COMPOSE_DIR = os.environ.get("TAIGA_DOCKER")
SUBPROCESS_TIMEOUT = 60
ADDON_TABLES = {
    "Component": "taiga_contrib_components_component",
    "Assignment": "taiga_contrib_components_assignment",
}
ALLOWED_CREATE_MODELS = set(ADDON_TABLES)
ALLOWED_MIGRATION_OPS = {"CreateModel", "RunSQL"}
COMPONENT_LOWER_NAME_INDEX = "taiga_contrib_components_component_project_lower_name_uniq"
OFFICIAL_TABLES = {
    "projects_project",
    "userstories_userstory",
}
# Underscore-bearing SQL idents the AC-2 RunSQL fence will accept. Table
# names come from ADDON_TABLES.values() so a rename cannot drift.
ALLOWED_SQL_IDENTS = set(ADDON_TABLES.values()) | {
    COMPONENT_LOWER_NAME_INDEX,
    "project_id",
    "userstory_id",
    "component_id",
}
EXPECTED_RELATED = {
    ("Component", "project"): "contrib_components",
    ("Assignment", "userstory"): "contrib_component_assignments",
    ("Assignment", "component"): "assignments",
}
INDEX_SQL = (
    f"CREATE UNIQUE INDEX {COMPONENT_LOWER_NAME_INDEX} "
    f"ON {ADDON_TABLES['Component']} (project_id, lower(name));"
)
INDEX_REVERSE_SQL = (
    f"DROP INDEX IF EXISTS {COMPONENT_LOWER_NAME_INDEX};"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sql_table_idents(sql: str) -> list[str]:
    """Identifiers that look like table/index/column names (contain `_`)."""
    return re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", sql.lower())


def _assert_sql_is_addon_only(sql: str) -> None:
    assert isinstance(sql, str)
    lower = sql.lower()
    assert "alter table" not in lower
    assert "drop table" not in lower
    for ident in _sql_table_idents(lower):
        assert ident not in OFFICIAL_TABLES, ident
        assert ident in ALLOWED_SQL_IDENTS, ident


def _attr_path(node: ast.AST) -> str:
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _attr_path(node.func)
    return ""


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _op_target_name(call: ast.Call) -> ast.AST | None:
    """Keyword `name`/`model_name`, else first positional arg (cannot wave through)."""
    target = _kw(call, "model_name") or _kw(call, "name")
    if target is not None:
        return target
    if call.args:
        return call.args[0]
    return None


def _createmodel_field_calls(call: ast.Call) -> dict[str, ast.Call]:
    fields_node = _kw(call, "fields")
    if fields_node is None and len(call.args) >= 2:
        fields_node = call.args[1]
    assert isinstance(fields_node, ast.List), "CreateModel fields missing"
    out: dict[str, ast.Call] = {}
    for elt in fields_node.elts:
        if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
            key, value = elt.elts
            if isinstance(value, ast.Call):
                out[str(_const(key))] = value
    return out


def _assert_ac2_operation(node: ast.AST) -> None:
    assert isinstance(node, ast.Call)
    op = _call_name(node).rsplit(".", 1)[-1]
    assert op in ALLOWED_MIGRATION_OPS, f"AC-2 default-deny: unexpected op {op}"
    if op == "CreateModel":
        name_node = _op_target_name(node)
        assert name_node is not None, "CreateModel has no name (keyword or positional)"
        assert _const(name_node) in ALLOWED_CREATE_MODELS
        return
    sql_node = _kw(node, "sql") or (node.args[0] if node.args else None)
    reverse_node = _kw(node, "reverse_sql")
    if reverse_node is None and len(node.args) >= 2:
        reverse_node = node.args[1]
    assert sql_node is not None
    assert reverse_node is not None
    _assert_sql_is_addon_only(_const(sql_node))
    _assert_sql_is_addon_only(_const(reverse_node))


def _assert_0001_initial_applied(stdout: str) -> None:
    lines = [ln for ln in stdout.splitlines() if "0001_initial" in ln]
    assert lines, stdout
    assert any(re.search(r"\[[Xx]\]", ln) for ln in lines), stdout


def _const(node: ast.AST):
    return ast.literal_eval(node)


def _on_delete_is_cascade(call: ast.Call) -> bool:
    node = _kw(call, "on_delete")
    if node is None:
        return False
    return _attr_path(node).endswith("CASCADE")


def _db_constraint(call: ast.Call) -> bool | None:
    node = _kw(call, "db_constraint")
    if node is None:
        return None
    return bool(_const(node))


def _class_assigns(class_node: ast.ClassDef) -> dict[str, ast.AST]:
    assigns: dict[str, ast.AST] = {}
    for item in class_node.body:
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
        ):
            assigns[item.targets[0].id] = item.value
    return assigns


def _model_classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def _nested_class(parent: ast.ClassDef, name: str) -> ast.ClassDef | None:
    for item in parent.body:
        if isinstance(item, ast.ClassDef) and item.name == name:
            return item
    return None


def _migration_assign(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Migration":
            assigns = _class_assigns(node)
            if name in assigns:
                return assigns[name]
    raise AssertionError(f"Migration.{name} not found")


def _module_imports(tree: ast.Module) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def _top_level_import_modules(tree: ast.Module) -> list[str]:
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


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


def _compose_exec(*manage_args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "taiga-back",
                "/opt/venv/bin/python",
                "manage.py",
                *manage_args,
            ],
            capture_output=True,
            text=True,
            cwd=COMPOSE_DIR,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"compose exec taiga-back unavailable: {exc}")


# --- A. Static / AST (no Django) ------------------------------------------------


def test_migration_package_exists():
    assert MIGRATION_INIT.is_file(), "migrations/__init__.py required or Django creates no tables"
    assert MIGRATION_0001.is_file(), "migrations/0001_initial.py missing"


def test_migration_dependencies_are_first_not_pinned():
    tree = ast.parse(_read(MIGRATION_0001))
    dependencies = _const(_migration_assign(tree, "dependencies"))
    assert dependencies == [
        ("projects", "__first__"),
        ("userstories", "__first__"),
    ]


def test_migration_operations_are_two_createmodel_and_runsql():
    tree = ast.parse(_read(MIGRATION_0001))
    operations = _migration_assign(tree, "operations")
    assert isinstance(operations, ast.List)
    names = [_call_name(node).rsplit(".", 1)[-1] for node in operations.elts]
    assert names == ["CreateModel", "CreateModel", "RunSQL"]
    created = []
    for node in operations.elts:
        if not isinstance(node, ast.Call):
            continue
        op = _call_name(node).rsplit(".", 1)[-1]
        if op == "CreateModel":
            name_node = _kw(node, "name")
            assert name_node is not None
            created.append(_const(name_node))
    assert set(created) == ALLOWED_CREATE_MODELS


def test_migration_ac2_fence_does_not_touch_official_tables():
    tree = ast.parse(_read(MIGRATION_0001))
    operations = _migration_assign(tree, "operations")
    assert isinstance(operations, ast.List)
    for node in operations.elts:
        _assert_ac2_operation(node)


def test_migration_lower_name_index_sql_and_reverse():
    tree = ast.parse(_read(MIGRATION_0001))
    operations = _migration_assign(tree, "operations")
    assert isinstance(operations, ast.List)
    runsql = [node for node in operations.elts if _call_name(node).endswith("RunSQL")]
    assert len(runsql) == 1
    sql = _const(_kw(runsql[0], "sql"))
    reverse = _const(_kw(runsql[0], "reverse_sql"))
    assert " ".join(sql.split()) == " ".join(INDEX_SQL.split())
    assert " ".join(reverse.split()) == " ".join(INDEX_REVERSE_SQL.split())


def test_models_ast_fk_guardrails_and_related_names():
    tree = ast.parse(_read(MODELS_PY))
    models = _model_classes(tree)
    assert set(models) >= {"Component", "Assignment"}

    component_fields = _class_assigns(models["Component"])
    assignment_fields = _class_assigns(models["Assignment"])

    project = component_fields["project"]
    userstory = assignment_fields["userstory"]
    component = assignment_fields["component"]
    assert isinstance(project, ast.Call)
    assert isinstance(userstory, ast.Call)
    assert isinstance(component, ast.Call)
    assert _attr_path(project.func).endswith("ForeignKey")
    assert _attr_path(userstory.func).endswith("ForeignKey")
    assert _attr_path(component.func).endswith("ForeignKey")

    assert _db_constraint(project) is False
    assert _db_constraint(userstory) is False
    assert _db_constraint(component) is not False
    assert _on_delete_is_cascade(project)
    assert _on_delete_is_cascade(userstory)
    assert _on_delete_is_cascade(component)
    assert _const(_kw(project, "related_name")) == EXPECTED_RELATED[("Component", "project")]
    assert _const(_kw(userstory, "related_name")) == EXPECTED_RELATED[("Assignment", "userstory")]
    assert _const(_kw(component, "related_name")) == EXPECTED_RELATED[("Assignment", "component")]

    project_to = project.args[0] if project.args else _kw(project, "to")
    userstory_to = userstory.args[0] if userstory.args else _kw(userstory, "to")
    component_to = component.args[0] if component.args else _kw(component, "to")
    assert _const(project_to) == "projects.Project"
    assert _const(userstory_to) == "userstories.UserStory"
    assert _const(component_to) == "Component"

    assert "project_id" not in component_fields
    assert "userstory_id" not in assignment_fields
    assert "component_id" not in assignment_fields

    name_field = component_fields["name"]
    order_field = component_fields["order"]
    assert isinstance(name_field, ast.Call)
    assert isinstance(order_field, ast.Call)
    assert _const(_kw(name_field, "max_length")) == 255
    assert _const(_kw(order_field, "default")) == 0


def test_models_ast_meta_ordering_and_assignment_unique():
    tree = ast.parse(_read(MODELS_PY))
    models = _model_classes(tree)
    component_meta = _nested_class(models["Component"], "Meta")
    assignment_meta = _nested_class(models["Assignment"], "Meta")
    assert component_meta is not None
    assert assignment_meta is not None
    component_opts = _class_assigns(component_meta)
    assignment_opts = _class_assigns(assignment_meta)
    assert _const(component_opts["ordering"]) == ("order", "id")
    assert "unique_together" not in assignment_opts
    constraints = assignment_opts["constraints"]
    assert isinstance(constraints, ast.List)
    assert len(constraints.elts) == 1
    uniq = constraints.elts[0]
    assert isinstance(uniq, ast.Call)
    assert _attr_path(uniq.func).endswith("UniqueConstraint")
    assert list(_const(_kw(uniq, "fields"))) == ["userstory", "component"]
    assert _const(_kw(uniq, "name")) == "taiga_contrib_components_assignment_uniq"


def test_apps_py_stays_django_apps_only_and_pins_autofield():
    tree = ast.parse(_read(APPS_PY))
    assert _top_level_import_modules(tree) == ["django.apps"]
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert len(classes) == 1
    assigns = {}
    for name, value in _class_assigns(classes[0]).items():
        assigns[name] = _const(value)
    assert assigns["name"] == "taiga_contrib_components"
    assert assigns["default_auto_field"] == "django.db.models.AutoField"
    assert assigns["default"] is True


def test_package_init_has_no_django_import():
    src = _read(INIT_PY)
    tree = ast.parse(src)
    for name in _module_imports(tree):
        assert name != "django" and not name.startswith("django.")
        assert name != "taiga" and not name.startswith("taiga.")


def test_ac2_sql_fence_rejects_official_core_tables():
    """Core tables are projects_project / userstories_userstory, not taiga_*."""
    sneaky_project = "UPDATE projects_project SET name = 'x'"
    sneaky_story = "DELETE FROM userstories_userstory WHERE id = 1"
    assert "projects_project" in _sql_table_idents(sneaky_project)
    assert "userstories_userstory" in _sql_table_idents(sneaky_story)
    with pytest.raises(AssertionError):
        _assert_sql_is_addon_only(sneaky_project)
    with pytest.raises(AssertionError):
        _assert_sql_is_addon_only(sneaky_story)


def test_ac2_fence_default_denies_unknown_ops_and_positional_targets():
    tree = ast.parse(
        "ops = [\n"
        "    migrations.RunPython(noop),\n"
        "    migrations.DeleteModel('Project'),\n"
        "    migrations.SeparateDatabaseAndState(),\n"
        "    migrations.AlterModelOptions(name='Component', options={}),\n"
        "]\n"
    )
    ops = tree.body[0].value
    assert isinstance(ops, ast.List)
    for node in ops.elts:
        with pytest.raises(AssertionError):
            _assert_ac2_operation(node)


def test_django_pin_records_python_ceiling():
    text = (REPO / "requirements-dev.txt").read_text(encoding="utf-8")
    assert re.search(
        r'^Django==3\.2\.25\s*;\s*python_version\s*<\s*["\']3\.13["\']\s*$',
        text,
        re.M,
    ), text


def test_migration_cross_boundary_fks_have_no_db_constraint():
    tree = ast.parse(_read(MIGRATION_0001))
    operations = _migration_assign(tree, "operations")
    assert isinstance(operations, ast.List)
    by_name: dict[str, dict[str, ast.Call]] = {}
    for node in operations.elts:
        if isinstance(node, ast.Call) and _call_name(node).endswith("CreateModel"):
            name_node = _op_target_name(node)
            assert name_node is not None
            by_name[str(_const(name_node))] = _createmodel_field_calls(node)
    project_fk = by_name["Component"]["project"]
    userstory_fk = by_name["Assignment"]["userstory"]
    component_fk = by_name["Assignment"]["component"]
    assert _db_constraint(project_fk) is False
    assert _db_constraint(userstory_fk) is False
    assert _db_constraint(component_fk) is not False


def test_addon_table_values_are_the_sql_allowlist_and_harness_source():
    assert set(ADDON_TABLES.values()) <= ALLOWED_SQL_IDENTS
    src = _read(HARNESS_CHILD)
    for table in ADDON_TABLES.values():
        assert table in src


def test_showmigrations_binds_applied_mark_to_0001():
    _assert_0001_initial_applied("taiga_contrib_components\n [X] 0001_initial\n")
    with pytest.raises(AssertionError):
        _assert_0001_initial_applied(" [ ] 0001_initial\n [X] 0002_later\n")
    with pytest.raises(AssertionError):
        _assert_0001_initial_applied(" [X] 0002_later\n")


# --- B. Django + SQLite harness ------------------------------------------------


def _write_stub_app(root: Path, label: str, model_name: str, extra_field: str) -> None:
    app = root / label
    migrations = app / "migrations"
    migrations.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "models.py").write_text(
        "from django.db import models\n\n"
        f"class {model_name}(models.Model):\n"
        f"    {extra_field} = models.CharField(max_length=50)\n",
        encoding="utf-8",
    )
    (migrations / "__init__.py").write_text("", encoding="utf-8")
    (migrations / "0001_initial.py").write_text(
        "from django.db import migrations, models\n\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n"
        "    dependencies = []\n"
        "    operations = [\n"
        "        migrations.CreateModel(\n"
        f'            name="{model_name}",\n'
        "            fields=[\n"
        '                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),\n'
        f'                ("{extra_field}", models.CharField(max_length=50)),\n'
        "            ],\n"
        "        ),\n"
        "    ]\n",
        encoding="utf-8",
    )


def test_django_sqlite_harness(tmp_path):
    """AC-1/3/4/5 against a real Django + SQLite database.

    The body runs in a child interpreter (`tests/_django_sqlite_harness.py`).
    `settings.configure()` / `django.setup()` are irreversible per-process
    globals: doing them here would mean whichever Django test 2.2 or 2.3 adds
    runs first silently disables the other. A child process gets a clean
    registry every time and takes its `sys.path` / `sys.modules` mutations to
    the grave with it, so this test neither leaks state nor depends on
    collection order.
    """
    if sys.version_info >= (3, 13):
        pytest.skip("Django 3.2.25 needs cgi (removed in Python 3.13)")
    pytest.importorskip("django")

    _write_stub_app(tmp_path, "projects", "Project", "name")
    _write_stub_app(tmp_path, "userstories", "UserStory", "subject")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(TAIGA_STUB), str(tmp_path), str(STUB_BACK), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    try:
        proc = subprocess.run(
            [sys.executable, str(HARNESS_CHILD), str(tmp_path)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Layer B harness exceeded {SUBPROCESS_TIMEOUT}s")

    assert proc.returncode == 0, (
        f"Layer B harness failed (exit {proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )


# --- C. Live container (skipif) ------------------------------------------------


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_live_showmigrations_addon_0001_applied():
    if not COMPOSE_DIR:
        pytest.skip("TAIGA_DOCKER unset; live migrate check needs official taiga-docker compose project")
    if not _overlay_exec_available():
        pytest.skip("overlay stack not running (compose exec taiga-back failed)")
    proc = _compose_exec("showmigrations", "taiga_contrib_components")
    assert proc.returncode == 0, proc.stderr
    _assert_0001_initial_applied(proc.stdout)


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker not installed")
def test_live_makemigrations_check_matches_models():
    if not COMPOSE_DIR:
        pytest.skip("TAIGA_DOCKER unset; live drift check needs official taiga-docker compose project")
    if not _overlay_exec_available():
        pytest.skip("overlay stack not running (compose exec taiga-back failed)")
    proc = _compose_exec(
        "makemigrations",
        "--check",
        "--dry-run",
        "taiga_contrib_components",
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
