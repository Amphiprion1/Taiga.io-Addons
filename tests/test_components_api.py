"""Story 2.2 — catalog REST wiring (Layer A AST) and live HTTP (Layer C)."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STUB_BACK = REPO / "addons" / "components" / "back"
STUB_APP = STUB_BACK / "taiga_contrib_components"
TAIGA_STUB = Path(__file__).resolve().parent / "_taiga_stub"
APPS_PY = STUB_APP / "apps.py"
API_PY = STUB_APP / "api.py"
PERMISSIONS_PY = STUB_APP / "permissions.py"
VALIDATORS_PY = STUB_APP / "validators.py"
SERIALIZERS_PY = STUB_APP / "serializers.py"
SERVICES_PY = STUB_APP / "services.py"
COMPOSE_DIR = os.environ.get("TAIGA_DOCKER")
SUBPROCESS_TIMEOUT = 60

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
from _addon_package import ALLOWED_STUB_APP_ENTRIES  # noqa: E402

EXPECTED_TAIGA_IMPORTS: dict[str, set[str]] = {
    "taiga.base": {"routers", "filters"},
    "taiga.urls": {"urlpatterns"},
    "taiga.base.api": {"validators", "serializers"},
    "taiga.base.exceptions": {"ValidationError"},
    "taiga.base.fields": {"Field"},
    "taiga.base.api.viewsets": {"ModelCrudViewSet"},
    "taiga.base.api.permissions": {"TaigaResourcePermission", "IsAuthenticated"},
    "taiga.permissions.permissions": {"HasProjectPerm", "IsProjectAdmin"},
    "taiga.projects.mixins.ordering": {"BulkUpdateOrderMixin"},
}

WRITE_PERMS = (
    "create_perms",
    "update_perms",
    "partial_update_perms",
    "destroy_perms",
    "bulk_update_order_perms",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _const(node: ast.AST):
    return ast.literal_eval(node)


def _attr_path(node: ast.AST) -> str:
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _class_by_name(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


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


def _nested_class(parent: ast.ClassDef, name: str) -> ast.ClassDef | None:
    for item in parent.body:
        if isinstance(item, ast.ClassDef) and item.name == name:
            return item
    return None


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    return None


def _arg_names(func: ast.FunctionDef) -> list[str]:
    return [arg.arg for arg in func.args.args]


def _returns_name(func: ast.FunctionDef, name: str) -> bool:
    returns = [node for node in ast.walk(func) if isinstance(node, ast.Return)]
    if not returns:
        return False
    for node in returns:
        if node.value is None or not isinstance(node.value, ast.Name):
            return False
        if node.value.id != name:
            return False
    return True


def _import_from_map(tree: ast.Module) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                mapping[alias.asname or alias.name] = node.module
    return mapping


def _top_level_import_modules(tree: ast.Module) -> list[str]:
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def _module_imports(tree: ast.Module) -> list[tuple[str, int, tuple[str, ...]]]:
    found: list[tuple[str, int, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.module, node.level, tuple(a.name for a in node.names)))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, 0, ()))
    return found


def _perm_src(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        name = _attr_path(node.func).rsplit(".", 1)[-1]
        if node.args:
            rendered = []
            for arg in node.args:
                try:
                    rendered.append(repr(_const(arg)))
                except Exception:
                    rendered.append(_attr_path(arg))
            return f"{name}({', '.join(rendered)})"
        return f"{name}()"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
        return f"{_perm_src(node.left)} & {_perm_src(node.right)}"
    raise AssertionError(f"unexpected perm expr: {ast.dump(node)}")


def _collect_addon_taiga_imports(root: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(_read(path))
        for module, level, names in _module_imports(tree):
            if level != 0:
                continue
            if module == "taiga" or module.startswith("taiga."):
                found.setdefault(module, set()).update(names)
    return found


def _stub_module_path(module: str) -> Path:
    rel = Path(*module.split("."))
    file_path = TAIGA_STUB / rel.with_suffix(".py")
    pkg_path = TAIGA_STUB / rel / "__init__.py"
    if file_path.is_file():
        return file_path
    if pkg_path.is_file():
        return pkg_path
    raise AssertionError(f"stub has no module {module}")


def _stub_defined_names(module: str) -> set[str]:
    tree = ast.parse(_read(_stub_module_path(module)))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _stub_child_modules(module: str) -> set[str]:
    rel = TAIGA_STUB / Path(*module.split("."))
    names: set[str] = set()
    if (rel / "__init__.py").is_file():
        for child in rel.iterdir():
            if child.name == "__pycache__" or child.name.startswith("."):
                continue
            if child.is_dir() and (child / "__init__.py").is_file():
                names.add(child.name)
            elif child.is_file() and child.suffix == ".py" and child.name != "__init__.py":
                names.add(child.stem)
    return names


def _stub_all_modules() -> set[str]:
    modules: set[str] = set()
    root = TAIGA_STUB / "taiga"
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(TAIGA_STUB)
        if path.name == "__init__.py":
            parts = rel.parent.parts
        else:
            parts = rel.with_suffix("").parts
        modules.add(".".join(parts))
    return modules


def _collect_used_attrs_on_taiga_imports(root: Path) -> dict[str, set[str]]:
    used: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(_read(path))
        alias_to_full: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module != "taiga" and not node.module.startswith("taiga."):
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                alias_to_full[local] = f"{node.module}.{alias.name}"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
                continue
            full = alias_to_full.get(node.value.id)
            if full:
                used.setdefault(full, set()).add(node.attr)
    return used


# --- A. Static / AST ------------------------------------------------------------


def test_package_file_allowlist():
    entries = {p.name for p in STUB_APP.iterdir() if p.name != "__pycache__"}
    assert entries == ALLOWED_STUB_APP_ENTRIES


def test_services_imports_no_taiga():
    tree = ast.parse(_read(SERVICES_PY))
    for module, _level, _names in _module_imports(tree):
        assert module != "taiga" and not module.startswith("taiga.")
    top: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level:
                top.append("." * node.level + node.module)
            else:
                top.append(node.module)
        elif isinstance(node, ast.Import):
            top.extend(alias.name for alias in node.names)
    assert top == ["django.db", ".models"]


def test_permissions_perms_table_and_import_sources():
    tree = ast.parse(_read(PERMISSIONS_PY))
    imported = _import_from_map(tree)
    assert imported["TaigaResourcePermission"] == "taiga.base.api.permissions"
    assert imported["IsAuthenticated"] == "taiga.base.api.permissions"
    assert imported["HasProjectPerm"] == "taiga.permissions.permissions"
    assert imported["IsProjectAdmin"] == "taiga.permissions.permissions"

    cls = _class_by_name(tree, "ComponentPermission")
    bases = [_attr_path(base) for base in cls.bases]
    assert any(base.endswith("TaigaResourcePermission") for base in bases)
    assigns = _class_assigns(cls)
    assert _perm_src(assigns["list_perms"]) == "IsAuthenticated()"
    assert _perm_src(assigns["retrieve_perms"]) == (
        "IsAuthenticated() & HasProjectPerm('view_project')"
    )
    for attr in WRITE_PERMS:
        assert _perm_src(assigns[attr]) == "IsProjectAdmin()"
    assert "enough_perms" not in assigns
    extra = set(assigns) - {
        "list_perms",
        "retrieve_perms",
        *WRITE_PERMS,
    }
    assert extra == set()


def test_api_viewset_shape_and_list_checks_permissions():
    tree = ast.parse(_read(API_PY))
    cls = _class_by_name(tree, "ComponentViewSet")
    bases = [_attr_path(base) for base in cls.bases]
    assert len(bases) == 2
    assert bases[0].endswith("ModelCrudViewSet")
    assert bases[1].endswith("BulkUpdateOrderMixin")
    assigns = _class_assigns(cls)
    assert _attr_path(assigns["model"]).endswith("Component")
    assert _attr_path(assigns["serializer_class"]).endswith("ComponentSerializer")
    assert _attr_path(assigns["validator_class"]).endswith("ComponentValidator")
    perm_classes = assigns["permission_classes"]
    assert isinstance(perm_classes, (ast.Tuple, ast.List))
    assert len(perm_classes.elts) == 1
    assert _attr_path(perm_classes.elts[0]).endswith("ComponentPermission")
    backends = assigns["filter_backends"]
    assert isinstance(backends, (ast.Tuple, ast.List))
    assert len(backends.elts) == 1
    assert _attr_path(backends.elts[0]).endswith("CanViewProjectFilterBackend")
    assert _const(assigns["filter_fields"]) == ("project",)
    assert _const(assigns["bulk_update_param"]) == "bulk_components"
    assert _const(assigns["bulk_update_perm"]) == "change_component"
    action = assigns["bulk_update_order_action"]
    assert isinstance(action, ast.Name), "reorder wrapper must live in api.py"
    assert action.id == "bulk_update_component_order"
    extra = set(assigns) - {
        "model",
        "serializer_class",
        "validator_class",
        "permission_classes",
        "filter_backends",
        "filter_fields",
        "bulk_update_param",
        "bulk_update_perm",
        "bulk_update_order_action",
    }
    assert extra == set(), extra

    wrapper = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "bulk_update_component_order":
            wrapper = node
    assert wrapper is not None
    assert _arg_names(wrapper) == ["project", "user", "data"]

    list_fn = _method(cls, "list")
    assert list_fn is not None
    called = False
    returns_super_list = False
    for node in ast.walk(list_fn):
        if isinstance(node, ast.Call) and _attr_path(node.func).endswith(
            "check_permissions"
        ):
            literals = []
            for arg in node.args:
                try:
                    literals.append(_const(arg))
                except Exception:
                    continue
            if "list" in literals:
                called = True
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr == "list":
                if isinstance(func.value, ast.Call):
                    callee = func.value.func
                    if isinstance(callee, ast.Name) and callee.id == "super":
                        returns_super_list = True
    assert called, "list() must call check_permissions(..., 'list', ...)"
    assert returns_super_list, "list() must return super().list(...)"


def test_apps_ready_registers_slashless_components_router():
    tree = ast.parse(_read(APPS_PY))
    assert _top_level_import_modules(tree) == ["django.apps"]
    cls = _class_by_name(tree, "ComponentsConfig")
    ready = _method(cls, "ready")
    assert ready is not None

    trailing = []
    register_prefixes = []
    path_prefixes = []
    for node in ast.walk(ready):
        if not isinstance(node, ast.Call):
            continue
        name = _attr_path(node.func)
        if name.endswith("DefaultRouter"):
            for keyword in node.keywords:
                if keyword.arg == "trailing_slash":
                    trailing.append(_const(keyword.value))
        elif name.endswith("register"):
            if node.args:
                register_prefixes.append(_const(node.args[0]))
            for keyword in node.keywords:
                if keyword.arg == "prefix":
                    register_prefixes.append(_const(keyword.value))
        elif name.endswith("path") and node.args:
            try:
                path_prefixes.append(_const(node.args[0]))
            except Exception:
                continue
    assert trailing == [False]
    assert register_prefixes == ["components"]
    assert "api/v1/" in path_prefixes


def test_validators_use_drf2_signature_and_return_attrs():
    tree = ast.parse(_read(VALIDATORS_PY))
    cls = _class_by_name(tree, "ComponentValidator")
    meta = _nested_class(cls, "Meta")
    assert meta is not None
    meta_assigns = _class_assigns(meta)
    assert _attr_path(meta_assigns["model"]).endswith("Component")
    assert _const(meta_assigns["fields"]) == ("id", "project", "name", "order")
    for method_name in ("validate_name", "validate_project"):
        func = _method(cls, method_name)
        assert func is not None, method_name
        assert _arg_names(func) == ["self", "attrs", "source"]
        assert _returns_name(func, "attrs"), method_name


def test_serializer_is_light_with_project_id_attr():
    tree = ast.parse(_read(SERIALIZERS_PY))
    cls = _class_by_name(tree, "ComponentSerializer")
    bases = [_attr_path(base) for base in cls.bases]
    assert any(base.endswith("LightSerializer") for base in bases)
    assigns = _class_assigns(cls)
    assert set(assigns) == {"id", "name", "order", "project"}
    for field_name in ("id", "name", "order"):
        call = assigns[field_name]
        assert isinstance(call, ast.Call)
        assert _attr_path(call.func).rsplit(".", 1)[-1] == "Field"
        assert all(kw.arg != "attr" for kw in call.keywords)
    project = assigns["project"]
    assert isinstance(project, ast.Call)
    assert _attr_path(project.func).rsplit(".", 1)[-1] == "Field"
    attr = None
    for keyword in project.keywords:
        if keyword.arg == "attr":
            attr = _const(keyword.value)
    assert attr == "project_id"


def test_taiga_stub_matches_addon_imports_exactly():
    actual = _collect_addon_taiga_imports(STUB_APP)
    assert actual == EXPECTED_TAIGA_IMPORTS

    for module, names in EXPECTED_TAIGA_IMPORTS.items():
        defined = _stub_defined_names(module)
        children = _stub_child_modules(module)
        provided = defined | children
        missing = names - provided
        extra = defined - names
        assert missing == set(), f"{module} stub missing {missing}"
        assert extra == set(), f"{module} stub extra symbols {extra}"

    imported_modules = set(EXPECTED_TAIGA_IMPORTS)
    parents: set[str] = set()
    name_modules: set[str] = set()
    for module in imported_modules:
        parts = module.split(".")
        for i in range(1, len(parts)):
            parents.add(".".join(parts[:i]))
        for name in EXPECTED_TAIGA_IMPORTS[module]:
            name_modules.add(f"{module}.{name}")
    allowed = imported_modules | parents | name_modules
    extras = _stub_all_modules() - allowed
    assert extras == set(), f"stub extra modules {extras}"

    used_attrs = _collect_used_attrs_on_taiga_imports(STUB_APP)
    for module in name_modules:
        try:
            defined = _stub_defined_names(module)
        except AssertionError:
            continue
        expected = used_attrs.get(module, set())
        extra_syms = defined - expected
        missing_syms = expected - defined
        assert extra_syms == set(), f"{module} stub extra symbols {extra_syms}"
        assert missing_syms == set(), f"{module} stub missing {missing_syms}"


def test_addon_does_not_reference_taiga_stub():
    for path in STUB_APP.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        assert "_taiga_stub" not in _read(path)


# --- C. Live container (skipif) -------------------------------------------------


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


def _compose_exec_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "taiga-back",
            "/opt/venv/bin/python",
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        cwd=COMPOSE_DIR,
        timeout=SUBPROCESS_TIMEOUT,
    )


def _require_overlay_stack() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker not installed")
    if not COMPOSE_DIR:
        pytest.skip(
            "TAIGA_DOCKER unset; live catalog HTTP needs official taiga-docker compose project"
        )
    if not _overlay_exec_available():
        pytest.skip("overlay stack not running (compose exec taiga-back failed)")


def test_live_anonymous_catalog_list_is_401():
    _require_overlay_stack()
    code = textwrap.dedent(
        """
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.overlay")
        import django
        django.setup()
        import urllib.error
        import urllib.request
        from django.conf import settings
        host = getattr(settings, "TAIGA_SITES_DOMAIN", None) or "localhost"
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/components?project=1",
            headers={"Host": host},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            print("STATUS:200")
        except urllib.error.HTTPError as exc:
            print(f"STATUS:{exc.code}")
        """
    ).strip()
    proc = _compose_exec_python(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines, proc.stdout or proc.stderr
    last = lines[-1]
    assert last == "STATUS:401", proc.stdout


def test_live_catalog_member_admin_and_delete_cascade():
    _require_overlay_stack()
    code = textwrap.dedent(
        """
        import json
        import os
        import secrets
        import uuid
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.overlay")
        import django
        django.setup()
        import urllib.error
        import urllib.request
        from django.conf import settings
        from taiga.projects.models import Membership, Project
        from taiga.users.models import User
        from taiga.userstories.models import UserStory
        from taiga_contrib_components.models import Assignment, Component

        host = getattr(settings, "TAIGA_SITES_DOMAIN", None) or "localhost"
        project = Project.objects.order_by("id").first()
        if project is None:
            print("SKIP:no-project")
            raise SystemExit(0)
        role = project.roles.order_by("id").first()
        if role is None:
            print("SKIP:no-role")
            raise SystemExit(0)

        suffix = uuid.uuid4().hex[:8]
        password = secrets.token_urlsafe(24)
        created_user_ids = []
        created_component_ids = []
        created_assignment_ids = []
        created_story_ids = []

        def make_user(prefix, is_admin):
            user = User.objects.create(
                username=f"{prefix}{suffix}",
                email=f"{prefix}{suffix}@example.test",
                full_name=prefix,
                is_active=True,
            )
            user.set_password(password)
            user.save()
            created_user_ids.append(user.id)
            Membership.objects.create(
                user=user,
                project=project,
                role=role,
                is_admin=is_admin,
                email=user.email,
            )
            return user

        def auth_header(username):
            payload = json.dumps(
                {"type": "normal", "username": username, "password": password}
            ).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/v1/auth",
                data=payload,
                headers={"Host": host, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            return f"Bearer {body['auth_token']}"

        def call(method, url, token=None, payload=None):
            data = None if payload is None else json.dumps(payload).encode()
            headers = {"Host": host}
            if token:
                headers["Authorization"] = token
            if payload is not None:
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read().decode()
                    return resp.status, json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode()
                try:
                    body = json.loads(raw) if raw else None
                except Exception:
                    body = raw
                return exc.code, body

        try:
            admin = make_user("c22admin", True)
            member = make_user("c22member", False)
            other = Project.objects.exclude(id=project.id).order_by("id").first()
            admin_tok = auth_header(admin.username)
            member_tok = auth_header(member.username)
            base = "http://127.0.0.1:8000/api/v1/components"

            status, body = call("GET", f"{base}?project={project.id}", member_tok)
            print(f"MEMBER_GET:{status}")

            status, body = call(
                "POST",
                base,
                member_tok,
                {"project": project.id, "name": f"blocked-{suffix}"},
            )
            print(f"MEMBER_POST:{status}")

            unique = f"LiveComp-{suffix}"
            status, body = call(
                "POST",
                base,
                admin_tok,
                {"project": project.id, "name": unique, "order": 1},
            )
            print(f"ADMIN_POST:{status}")
            if status == 201 and isinstance(body, dict) and body.get("id"):
                created_component_ids.append(body["id"])
                pk = body["id"]
                status, _ = call("PATCH", f"{base}/{pk}", member_tok, {"name": "nope"})
                print(f"MEMBER_PATCH:{status}")
                status, _ = call("DELETE", f"{base}/{pk}", member_tok)
                print(f"MEMBER_DELETE:{status}")
                status, _ = call(
                    "POST",
                    f"{base}/bulk_update_order",
                    member_tok,
                    {"project": project.id, "bulk_components": [[pk, 2]]},
                )
                print(f"MEMBER_REORDER:{status}")
                status, _ = call(
                    "POST",
                    base,
                    admin_tok,
                    {"project": project.id, "name": unique.lower()},
                )
                print(f"ADMIN_DUP:{status}")
                if other is not None:
                    status, other_body = call(
                        "POST",
                        base,
                        admin_tok,
                        {"project": other.id, "name": f"xproj-{suffix}"},
                    )
                    print(f"ADMIN_OTHER:{status}")
                    if (
                        status == 201
                        and isinstance(other_body, dict)
                        and other_body.get("id")
                    ):
                        created_component_ids.append(other_body["id"])
                else:
                    print("ADMIN_OTHER:SKIP")

                story = UserStory.objects.filter(project=project).order_by("id").first()
                if story is None:
                    story = UserStory.objects.create(
                        project=project, subject=f"c22-{suffix}"
                    )
                    created_story_ids.append(story.id)
                doomed = Component.objects.create(
                    project=project, name=f"Doomed-{suffix}"
                )
                created_component_ids.append(doomed.id)
                assignment = Assignment.objects.create(
                    userstory=story, component=doomed
                )
                created_assignment_ids.append(assignment.id)
                status, _ = call("DELETE", f"{base}/{doomed.id}", admin_tok)
                gone = not Assignment.objects.filter(id=assignment.id).exists()
                story_ok = UserStory.objects.filter(pk=story.id).exists()
                print(f"DELETE_CASCADE:{status}:{int(gone)}:{int(story_ok)}")
            else:
                print("ADMIN_POST_BODY_MISSING")
        finally:
            Assignment.objects.filter(id__in=created_assignment_ids).delete()
            Component.objects.filter(id__in=created_component_ids).delete()
            Membership.objects.filter(user_id__in=created_user_ids).delete()
            User.objects.filter(id__in=created_user_ids).delete()
            if created_story_ids:
                UserStory.objects.filter(id__in=created_story_ids).delete()
        """
    ).strip()
    proc = _compose_exec_python(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = proc.stdout
    if "SKIP:no-project" in out or "SKIP:no-role" in out:
        pytest.skip(out.strip().splitlines()[-1])
    assert "MEMBER_GET:200" in out, out
    assert "MEMBER_POST:403" in out, out
    assert "MEMBER_PATCH:403" in out, out
    assert "MEMBER_DELETE:403" in out, out
    assert "MEMBER_REORDER:403" in out, out
    assert "ADMIN_POST:201" in out, out
    assert "ADMIN_DUP:400" in out, out
    if "ADMIN_OTHER:SKIP" not in out:
        assert "ADMIN_OTHER:403" in out, out
    assert "DELETE_CASCADE:204:1:1" in out, out
