from django.utils import timezone
from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from farmacia.models.online_order import OnlineOrder, OnlineOrderItem


def effective_status(order):
    """A reserved order past its hold reads as expired before the
    expire_online_orders command records it (its reservation already stopped
    holding stock). Reading never writes."""
    if order.status == OnlineOrder.STATUS_RESERVED and order.expires_at <= timezone.now():
        return OnlineOrder.STATUS_EXPIRED
    return order.status


class OnlineOrderItemSerializer(BaseSerializer):
    class Meta:
        model = OnlineOrderItem
        fields = ["id", "catalog_item", "medicine_name", "quantity", "unit_price", "prescription_required"]
        read_only_fields = fields


class OnlineOrderSerializer(BaseSerializer):
    """The pharmacy's view of an order (read only: orders change only through
    online_order_service)."""

    items = OnlineOrderItemSerializer(many=True, read_only=True)
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = OnlineOrder
        exclude = ["idempotency_key"]
        read_only_fields = [field.name for field in OnlineOrder._meta.fields]

    def get_effective_status(self, order):
        return effective_status(order)
