from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.alergiamedicamentosa import AlergiaMedicamentosa
from saude.serializers.alergiamedicamentosa import AlergiaMedicamentosaSerializer


@registerView("alergiamedicamentosas")
class AlergiaMedicamentosaAPIView(BaseAPIView):

    queryset = AlergiaMedicamentosa.objects.all()
    serializer_class = AlergiaMedicamentosaSerializer

