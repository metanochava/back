from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.exceptions import ConflictError

from hospitality.models import PrepStation
from hospitality.serializers import PrepStationSerializer


@registerView("prepstations")
class PrepStationAPIView(BaseAPIView):
    """The branch's preparation stations (kitchen, bar) and the catalogue
    categories each one prepares."""

    queryset = PrepStation.objects.all()
    serializer_class = PrepStationSerializer

    def perform_destroy(self, instance):
        if instance.tickets.exists():
            raise ConflictError("A station with tickets cannot be deleted; make it inactive.", code="station_in_use")
        super().perform_destroy(instance)
