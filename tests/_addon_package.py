"""Single source of truth for the addon package file allowlist."""

ALLOWED_STUB_APP_ENTRIES = frozenset(
    {
        "__init__.py",
        "apps.py",
        "models.py",
        "api.py",
        "serializers.py",
        "validators.py",
        "permissions.py",
        "services.py",
        "migrations",
    }
)
