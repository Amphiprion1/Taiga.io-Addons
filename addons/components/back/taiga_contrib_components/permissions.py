from taiga.base.api.permissions import IsAuthenticated
from taiga.base.api.permissions import TaigaResourcePermission
from taiga.permissions.permissions import HasProjectPerm
from taiga.permissions.permissions import IsProjectAdmin


class ComponentPermission(TaigaResourcePermission):
    list_perms = IsAuthenticated()
    retrieve_perms = IsAuthenticated() & HasProjectPerm("view_project")
    create_perms = IsProjectAdmin()
    update_perms = IsProjectAdmin()
    partial_update_perms = IsProjectAdmin()
    destroy_perms = IsProjectAdmin()
    bulk_update_order_perms = IsProjectAdmin()
