from rest_framework import serializers

from django_resaas.engine.core.base.serializers import BaseSerializer
from sales.models.customer import Customer


class CustomerSerializer(BaseSerializer):

    class Meta:
        model = Customer
        fields = "__all__"

    def validate(self, attrs):
        customer_type = attrs.get(
            "customer_type",
            getattr(self.instance, "customer_type", None)
        )

        person = attrs.get(
            "person",
            getattr(self.instance, "person", None)
        )

        company_name = attrs.get(
            "company_name",
            getattr(self.instance, "company_name", None)
        )

        if customer_type == Customer.TYPE_INDIVIDUAL:
            if not person or company_name:
                raise serializers.ValidationError(
                    "Cliente individual requer 'person' e não pode ter 'company_name'."
                )

        elif customer_type == Customer.TYPE_COMPANY:
            if not company_name or person:
                raise serializers.ValidationError(
                    "Cliente empresa requer 'company_name' e não pode ter 'person'."
                )

        else:
            raise serializers.ValidationError(
                "customer_type deve ser 'individual' ou 'company'."
            )

        return attrs
