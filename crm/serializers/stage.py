from rest_framework import serializers
from django_resaas.saas.core.base.serializers import BaseSerializer
from crm.models import Stage


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
