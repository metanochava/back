from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from crm import services
from crm.models import Lead
from crm.serializers._common import _entity_id


class LeadSerializer(BaseSerializer):
    """status changes go through the lead actions (qualify, disqualify, ...)."""

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Lead
        fields = "__all__"
        read_only_fields = ["status", "disqualify_reason"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        entity_id = _entity_id(self)
        if entity_id and "owner" in attrs:
            services.validate_user(attrs["owner"], entity_id, "owner")
        return attrs
