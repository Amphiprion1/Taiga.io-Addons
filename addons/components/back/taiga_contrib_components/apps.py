from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = "taiga_contrib_components"
    verbose_name = "Components"
    default = True
    default_auto_field = "django.db.models.AutoField"
