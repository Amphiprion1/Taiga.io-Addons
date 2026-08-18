from django.utils.translation import gettext as _
from taiga.base import filters
from taiga.base.api.viewsets import ModelCrudViewSet
from taiga.base.exceptions import ValidationError
from taiga.projects.mixins.ordering import BulkUpdateOrderMixin

from . import models
from . import permissions
from . import serializers
from . import services
from . import validators


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def bulk_update_component_order(project, user, data):
    if not isinstance(data, (list, tuple)):
        raise ValidationError(_("Invalid bulk_components payload."))
    pairs = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValidationError(_("Invalid bulk_components payload."))
        component_id, order = item
        if not _is_int(component_id) or not _is_int(order):
            raise ValidationError(_("Invalid bulk_components payload."))
        pairs.append((component_id, order))
    return services.bulk_update_component_order(project, user, pairs)


class ComponentViewSet(ModelCrudViewSet, BulkUpdateOrderMixin):
    model = models.Component
    serializer_class = serializers.ComponentSerializer
    validator_class = validators.ComponentValidator
    permission_classes = (permissions.ComponentPermission,)
    filter_backends = (filters.CanViewProjectFilterBackend,)
    filter_fields = ("project",)
    bulk_update_param = "bulk_components"
    bulk_update_perm = "change_component"
    bulk_update_order_action = bulk_update_component_order

    def list(self, request, *args, **kwargs):
        self.check_permissions(request, "list", None)
        return super().list(request, *args, **kwargs)
