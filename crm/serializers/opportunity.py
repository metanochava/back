from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from crm import services
from crm.models import Opportunity
from crm.serializers._common import _entity_id


class OpportunitySerializer(BaseSerializer):
    """stage / status / closing fields change through the `move` action."""

    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = "__all__"
        read_only_fields = ["status", "lost_reason", "closed_at", "lead"]

    def get_customer_name(self, obj):
        return services.customer_name(obj.customer_id, obj.entity_id)

    def get_fields(self):
        fields = super().get_fields()
        # the stage is chosen on creation; afterwards only `move` changes it
        if self.instance is not None and not isinstance(self.instance, (list, tuple)) and "stage" in fields:
            fields["stage"].read_only = True
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        entity_id = _entity_id(self)
        if not entity_id:
            return attrs
        if "owner" in attrs:
            services.validate_user(attrs["owner"], entity_id, "owner")
        if attrs.get("customer_id"):
            services.validate_customer(attrs["customer_id"], entity_id)
        stage = attrs.get("stage")
        if stage is not None and (stage.is_won or stage.is_lost):
            raise serializers.ValidationError({"stage": ["Choose an open stage."]})
        if attrs.get("amount") is not None and attrs["amount"] < 0:
            raise serializers.ValidationError({"amount": ["Amounts cannot be negative."]})
        return attrs
