from django.db import transaction

from .models import Component


def normalize_name(name):
    if name is None:
        return ""
    return name.strip()


def name_conflicts(project_id, name, exclude_pk=None):
    qs = Component.objects.filter(
        project_id=project_id,
        name__iexact=normalize_name(name),
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


@transaction.atomic
def bulk_update_component_order(project, user, data):
    for component_id, order in data:
        Component.objects.filter(project_id=project.id, id=component_id).update(
            order=order
        )
