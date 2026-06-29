from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView

from saude.models.imunizacao import Imunizacao
from saude.serializers.imunizacao import ImunizacaoSerializer


@registerView("imunizacaos")
class ImunizacaoAPIView(BaseAPIView):

    queryset = Imunizacao.objects.all()
    serializer_class = ImunizacaoSerializer
