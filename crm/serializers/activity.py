from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from crm import services
from crm.models import Activity
from crm.serializers._common import _entity_id


class ActivitySerializer(BaseSerializer):
    done = serializers.BooleanField(read_only=True)

    class Meta:
        model = Activity
        fields = "__all__"
        read_only_fields = ["completed_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        opportunity = attrs.get("opportunity", getattr(self.instance, "opportunity", None))
        if lead is None and opportunity is None:
            raise serializers.ValidationError({"lead": ["Link the activity to a lead or an opportunity."]})
        entity_id = _entity_id(self)
        if entity_id and "assigned_to" in attrs:
            services.validate_user(attrs["assigned_to"], entity_id, "assigned_to")
        return attrs
