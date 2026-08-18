from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("projects", "__first__"),
        ("userstories", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="Component",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("order", models.IntegerField(default=0)),
                (
                    "project",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrib_components",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ("order", "id"),
            },
        ),
        migrations.CreateModel(
            name="Assignment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "userstory",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrib_component_assignments",
                        to="userstories.userstory",
                    ),
                ),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="taiga_contrib_components.component",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["userstory", "component"],
                        name="taiga_contrib_components_assignment_uniq",
                    )
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX taiga_contrib_components_component_project_lower_name_uniq "
                "ON taiga_contrib_components_component (project_id, lower(name));"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS taiga_contrib_components_component_project_lower_name_uniq;"
            ),
        ),
    ]
