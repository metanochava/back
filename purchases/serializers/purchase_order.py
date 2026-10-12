from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from purchases.models import PurchaseOrder


class PurchaseOrderSerializer(BaseSerializer):
    """number, status, total and the submit/approve/cancel audit fields are
    written by purchases.services only."""

    supplier_label = serializers.CharField(read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = "__all__"
        read_only_fields = [
            "number",
            "status",
            "total",
            "submitted_at",
            "submitted_by",
            "approved_at",
            "approved_by",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
        ]
