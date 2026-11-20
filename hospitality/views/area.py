from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.exceptions import ConflictError

from hospitality.models import DiningArea
from hospitality.serializers import DiningAreaSerializer


@registerView("diningareas")
class DiningAreaAPIView(BaseAPIView):
    queryset = DiningArea.objects.all()
    serializer_class = DiningAreaSerializer

    def perform_destroy(self, instance):
        if instance.tables.exists():
            raise ConflictError("An area with tables cannot be deleted; make it inactive.", code="area_in_use")
        super().perform_destroy(instance)
