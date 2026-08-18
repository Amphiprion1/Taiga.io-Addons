from taiga.base import filters
from taiga.base.api.viewsets import ModelCrudViewSet
from taiga.projects.mixins.ordering import BulkUpdateOrderMixin

from . import models
from . import permissions
from . import serializers
from . import services
from . import validators


class ComponentViewSet(ModelCrudViewSet, BulkUpdateOrderMixin):
    model = models.Component
    serializer_class = serializers.ComponentSerializer
    validator_class = validators.ComponentValidator
    permission_classes = (permissions.ComponentPermission,)
    filter_backends = (filters.CanViewProjectFilterBackend,)
    filter_fields = ("project",)
    bulk_update_param = "bulk_components"
    bulk_update_perm = "change_component"
    bulk_update_order_action = services.bulk_update_component_order

    def list(self, request, *args, **kwargs):
        self.check_permissions(request, "list", None)
        return super().list(request, *args, **kwargs)
