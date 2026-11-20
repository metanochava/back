from rest_framework import serializers

from django_resaas.saas.core.base.serializers import BaseSerializer
from hospitality.models import DiningArea, DiningTable, PrepStation, PrepTicket, TableOrder, TableRequest


def _unique_in_branch(serializer, model, name):
    """The name is unique per branch (the view sets the branch from the
    request, so the database constraint is checked here first: 400, not 500)."""
    request = serializer.context.get("request")
    branch_id = getattr(serializer.instance, "branch_id", None) or getattr(request, "branch_id", None)
    if not name or not branch_id:
        return name
    clash = model.objects.filter(branch_id=branch_id, name__iexact=name.strip())
    if serializer.instance is not None:
        clash = clash.exclude(pk=serializer.instance.pk)
    if clash.exists():
        raise serializers.ValidationError("This name is already used in this branch.")
    return name.strip()


class DiningAreaSerializer(BaseSerializer):
    class Meta:
        model = DiningArea
        fields = "__all__"

    def validate_name(self, name):
        return _unique_in_branch(self, DiningArea, name)


class DiningTableSerializer(BaseSerializer):
    """qr_token and current_sale_id are written by hospitality.services only
    (rotate_qr, start_tab), never by the client."""

    class Meta:
        model = DiningTable
        fields = "__all__"
        read_only_fields = ["qr_token", "current_sale_id"]

    def validate_name(self, name):
        return _unique_in_branch(self, DiningTable, name)

    def validate_area(self, area):
        request = self.context.get("request")
        if area is not None and request is not None and str(area.entity_id) != str(getattr(request, "entity_id", "")):
            raise serializers.ValidationError("Does not belong to the current entity.")
        return area


class TableRequestSerializer(BaseSerializer):
    table_name = serializers.CharField(source="table.name", read_only=True)

    class Meta:
        model = TableRequest
        fields = "__all__"
        read_only_fields = ["table", "kind", "status", "handled_by", "handled_at"]


class PrepStationSerializer(BaseSerializer):
    class Meta:
        model = PrepStation
        fields = "__all__"

    def validate_name(self, name):
        return _unique_in_branch(self, PrepStation, name)

    def validate_category_ids(self, value):
        """A list of catalogue category ids (strings); only the Entity's count."""
        import uuid as _uuid
        if not isinstance(value, list):
            raise serializers.ValidationError("Choose the categories.")
        ids = []
        for item in value:
            raw = item.get("value") if isinstance(item, dict) else item
            try:
                ids.append(str(_uuid.UUID(str(raw))))
            except (ValueError, TypeError):
                raise serializers.ValidationError("Choose valid categories.")
        return sorted(set(ids))


class PrepTicketSerializer(BaseSerializer):
    class Meta:
        model = PrepTicket
        fields = "__all__"


class TableOrderSerializer(BaseSerializer):
    table_name = serializers.CharField(source="table.name", read_only=True)

    class Meta:
        model = TableOrder
        fields = "__all__"
