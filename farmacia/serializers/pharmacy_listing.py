import re

from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.pharmacy_listing import PharmacyListing


class PharmacyListingSerializer(BaseSerializer):

    class Meta:
        model = PharmacyListing
        fields = "__all__"

    def validate_currency(self, value):
        value = (value or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise serializers.ValidationError("Use the three-letter currency code (e.g. MZN).")
        return value

    def validate(self, attrs):
        # one listing per Branch: the Branch is the current one (context)
        request = self.context.get("request")
        if self.instance is None and request is not None:
            # deleted rows too: the unique constraint still sees them
            existing = PharmacyListing.all_objects.filter(branch_id=request.branch_id).first()
            if existing is not None and existing.deleted_at:
                raise serializers.ValidationError("This branch has a deleted marketplace listing: restore it.")
            if existing is not None:
                raise serializers.ValidationError("This branch already has a marketplace listing.")
        return attrs
