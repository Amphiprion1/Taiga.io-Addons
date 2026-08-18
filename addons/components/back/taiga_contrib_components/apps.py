from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = "taiga_contrib_components"
    verbose_name = "Components"
    default = True
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        from django.urls import include, path
        from taiga.base import routers
        from taiga.urls import urlpatterns
        from .api import ComponentViewSet

        router = routers.DefaultRouter(trailing_slash=False)
        router.register(r"components", ComponentViewSet, base_name="components")
        urlpatterns.append(path("api/v1/", include(router.urls)))
