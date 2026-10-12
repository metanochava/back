from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from purchases.models import Supplier


class SupplierSerializer(BaseSerializer):

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Supplier
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)

        supplier_type = attrs.get("supplier_type", getattr(self.instance, "supplier_type", None))
        person = attrs.get("person", getattr(self.instance, "person", None))
        company_name = attrs.get("company_name", getattr(self.instance, "company_name", None))

        if supplier_type == Supplier.TYPE_INDIVIDUAL and not person:
            raise serializers.ValidationError({"person": ["This field is required."]})
        if supplier_type == Supplier.TYPE_COMPANY and not (company_name or "").strip():
            raise serializers.ValidationError({"company_name": ["This field is required."]})

        return attrs
