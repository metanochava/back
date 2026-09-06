from django_resaas.engine.core.base.views import BaseAPIView, registerView
from farmacia.models.dispensa import Dispensa
from farmacia.serializers.dispensa import DispensaSerializer


@registerView("dispensas")
class DispensaAPIView(BaseAPIView):
    queryset = Dispensa.objects.all()
    serializer_class = DispensaSerializer
