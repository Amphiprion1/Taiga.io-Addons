from taiga.base.api import serializers
from taiga.base.fields import Field


class ComponentSerializer(serializers.LightSerializer):
    id = Field()
    name = Field()
    order = Field()
    project = Field(attr="project_id")
