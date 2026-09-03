from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.consultorio import Consultorio
from saude.serializers.consultorio import ConsultorioSerializer


@registerView("consultorios")
class ConsultorioAPIView(BaseAPIView):

    queryset = Consultorio.objects.all()
    serializer_class = ConsultorioSerializer
