from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.exceptions import ConflictError
from inventory import services
from inventory.models.batch import Batch
from inventory.serializers.batch import BatchSerializer


@registerView("batches")
class BatchAPIView(BaseAPIView):
    """Lots of products with batch tracking. Usually created by a goods
    receipt (purchases) or a stock movement; a lot with movements cannot be
    deleted."""

    queryset = Batch.objects.select_related("product")
    serializer_class = BatchSerializer

    def perform_destroy(self, instance):
        if instance.movements.exists():
            raise ConflictError("A lot with movements cannot be deleted.", code="batch_in_use")
        super().perform_destroy(instance)

    @resaas_action(
        methods=["get"], detail=False, label="Expiring", icon="event_busy",
        tooltip="Lots with stock that expire soon or are expired", position="l", order=10,
    )
    def expiring(self, request):
        """GET ?days=30&warehouse=<id> - current Entity only."""
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            raise ValidationError({"days": ["Enter a whole number."]})
        if days < 0 or days > 3650:
            raise ValidationError({"days": ["Enter a whole number."]})
        return Response(services.expiring_batches(request.entity_id, days, request.query_params.get("warehouse")))
