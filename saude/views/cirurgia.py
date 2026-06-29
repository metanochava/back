from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView

from saude.models.cirurgia import Cirurgia
from saude.serializers.cirurgia import CirurgiaSerializer


@registerView("cirurgias")
class CirurgiaAPIView(BaseAPIView):

    queryset = Cirurgia.objects.all()
    serializer_class = CirurgiaSerializer
