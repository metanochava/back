from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import all

from hospitality import services
from hospitality.models import TableOrder
from hospitality.serializers import TableOrderSerializer


def _drf(exc):
    return DRFValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)


@registerView("tableorders")
class TableOrderAPIView(BaseAPIView):
    """What customers ordered from the tables' QR pages (created by the QR
    page only): accept puts it on the table's tab, reject charges nothing."""

    queryset = TableOrder.objects.select_related("table").prefetch_related("lines").all()
    serializer_class = TableOrderSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed("POST")

    @resaas_action(methods=["post"], detail=True, label="Accept", icon="done",
                   tooltip="Put the order on the table's tab", position="t", order=10)
    def accept(self, request, pk=None):
        try:
            order = services.accept_order(order=self.get_object(), user=request.user)
        except DjangoValidationError as exc:
            raise _drf(exc)
        return all(request, data={"id": str(order.id), "status": order.status})

    @resaas_action(methods=["post"], detail=True, label="Reject", icon="close",
                   tooltip="Refuse the order: nothing is charged", position="t", order=20)
    def reject(self, request, pk=None):
        try:
            order = services.reject_order(order=self.get_object(), user=request.user)
        except DjangoValidationError as exc:
            raise _drf(exc)
        return all(request, data={"id": str(order.id), "status": order.status})
