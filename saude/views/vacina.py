from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView

from saude.models.vacina import Vacina
from saude.serializers.vacina import VacinaSerializer


@registerView("vacinas")
class VacinaAPIView(BaseAPIView):

    queryset = Vacina.objects.all()
    serializer_class = VacinaSerializer
