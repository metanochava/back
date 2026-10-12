from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from inventory.models.reservation import StockReservation


class StockReservationSerializer(BaseSerializer):
    """Input validation and reading only: reservations are written by
    inventory.services.reserve() (availability check under a row lock)."""

    class Meta:
        model = StockReservation
        fields = "__all__"
        read_only_fields = ["status"]
        extra_kwargs = {"source_type": {"required": False}, "source_id": {"required": False}}
