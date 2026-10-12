import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.exceptions import ConflictError

from inventory import services
from inventory.models.reservation import StockReservation
from inventory.serializers.reservation import StockReservationSerializer


@registerView("stockreservations")
class StockReservationAPIView(BaseAPIView):
    """Reservations of the Entity. POST creates a manual one (source "manual"
    unless given); a reservation is never edited - it is released."""

    queryset = StockReservation.objects.select_related("product", "warehouse")
    serializer_class = StockReservationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            reservation = services.reserve(
                product=data["product"],
                warehouse=data["warehouse"],
                quantity=data["quantity"],
                source_type=data.get("source_type") or "manual",
                source_id=data.get("source_id") or str(uuid.uuid4()),
                expires_at=data.get("expires_at"),
                reason=data.get("reason"),
                entity_id=request.entity_id,
                branch_id=request.branch_id,
                user=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"quantity": exc.messages})
        return Response(self.get_serializer(reservation).data, status=201)

    @resaas_action(
        methods=["post"], detail=True, label="Release", icon="lock_open",
        tooltip="Release the reserved stock", position="t", order=10, autorequest=True,
    )
    def release(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status != StockReservation.STATUS_ACTIVE:
            raise ConflictError("This reservation is no longer active.", code="reservation_not_active")
        reservation.status = StockReservation.STATUS_RELEASED
        reservation.updated_by = request.user
        reservation.save(update_fields=["status", "updated_by", "updated_at"])
        return Response(self.get_serializer(reservation).data)
