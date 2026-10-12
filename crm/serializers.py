from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer

from crm import services
from crm.models import Activity, Lead, Opportunity, Stage


def _entity_id(serializer):
    return getattr(serializer.context.get("request"), "entity_id", None)


class StageSerializer(BaseSerializer):
    class Meta:
        model = Stage
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        won = attrs.get("is_won", getattr(self.instance, "is_won", False))
        lost = attrs.get("is_lost", getattr(self.instance, "is_lost", False))
        if won and lost:
            raise serializers.ValidationError({"is_lost": ["A stage cannot be won and lost."]})
        probability = attrs.get("probability")
        if probability is not None and probability > 100:
            raise serializers.ValidationError({"probability": ["Enter a percentage between 0 and 100."]})
        return attrs


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
