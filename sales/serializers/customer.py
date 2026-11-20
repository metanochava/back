from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
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

        # each rule names its field, so a form shows it at the field
        if customer_type == Customer.TYPE_INDIVIDUAL:
            errors = {}
            if not person:
                errors["person"] = ["An individual customer needs a person."]
            if company_name:
                errors["company_name"] = ["An individual customer has no company name."]
            if errors:
                raise serializers.ValidationError(errors)
        elif customer_type == Customer.TYPE_COMPANY:
            errors = {}
            if not company_name:
                errors["company_name"] = ["A company customer needs its name."]
            if person:
                errors["person"] = ["A company customer has no person."]
            if errors:
                raise serializers.ValidationError(errors)
        else:
            raise serializers.ValidationError({"customer_type": ["Choose individual or company."]})

        # price_list_id must be one of the Entity's price lists (catalog)
        price_list_id = attrs.get("price_list_id")
        request = self.context.get("request")
        if price_list_id and request is not None and getattr(request, "entity_id", None):
            from sales import services

            if not services.price_list_snapshot(price_list_id, request.entity_id):
                raise serializers.ValidationError({"price_list_id": ["Does not belong to the current entity."]})

        return attrs
