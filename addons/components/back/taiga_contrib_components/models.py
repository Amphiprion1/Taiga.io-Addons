from django.db import models


class Component(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="contrib_components",
        db_constraint=False,
    )
    name = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)


class Assignment(models.Model):
    userstory = models.ForeignKey(
        "userstories.UserStory",
        on_delete=models.CASCADE,
        related_name="contrib_component_assignments",
        db_constraint=False,
    )
    component = models.ForeignKey(
        "Component",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["userstory", "component"],
                name="taiga_contrib_components_assignment_uniq",
            )
        ]
