from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators import resaas_action
from django_resaas.saas.core.utils import all

from hospitality import services
from hospitality.models import TableRequest
from hospitality.serializers import TableRequestSerializer


@registerView("tablerequests")
class TableRequestAPIView(BaseAPIView):
    """What customers asked from the tables' QR pages (read-only: they are
    created by the QR page) and marking one handled."""

    queryset = TableRequest.objects.select_related("table").all()
    serializer_class = TableRequestSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed("POST")

    @resaas_action(methods=["post"], detail=True, label="Handled", icon="done",
                   tooltip="Mark the request handled", position="t", order=10)
    def handle(self, request, pk=None):
        handled = services.handle_request(request=self.get_object(), user=request.user)
        return all(request, data=self.get_serializer(handled).data)
