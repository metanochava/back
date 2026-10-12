from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from sales.models.tax import Tax


class TaxSerializer(BaseSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Tax
        fields = "__all__"

    def validate_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Enter a percentage between 0 and 100.")
        return value
