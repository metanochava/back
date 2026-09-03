from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.observacaoclinica import ObservacaoClinica
from saude.serializers.observacaoclinica import ObservacaoClinicaSerializer


@registerView("observacoesclinicas")
class ObservacaoClinicaAPIView(BaseAPIView):

    queryset = ObservacaoClinica.objects.all()
    serializer_class = ObservacaoClinicaSerializer

