from django.utils.translation import gettext as _
from taiga.base.api import validators
from taiga.base.exceptions import ValidationError

from . import models
from . import services


class ComponentValidator(validators.ModelValidator):
    class Meta:
        model = models.Component
        fields = ("id", "project", "name", "order")

    def validate_name(self, attrs, source):
        if source not in attrs or attrs[source] is None:
            return attrs
        normalized = services.normalize_name(attrs[source])
        if not normalized:
            raise ValidationError(_("Name cannot be empty."))
        attrs[source] = normalized

        project = attrs.get("project")
        if project is None and self.object is not None:
            project = self.object.project
        if project is None:
            return attrs

        project_id = project.pk if hasattr(project, "pk") else project
        exclude_pk = self.object.pk if self.object is not None else None
        if services.name_conflicts(project_id, normalized, exclude_pk=exclude_pk):
            raise ValidationError(
                _("A component with this name already exists in this project.")
            )
        return attrs

    def validate_project(self, attrs, source):
        if self.object is not None and source in attrs:
            new_project = attrs[source]
            new_id = new_project.pk if hasattr(new_project, "pk") else new_project
            if new_id != self.object.project_id:
                raise ValidationError(_("Cannot move a component to another project."))
        return attrs
