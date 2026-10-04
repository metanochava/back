from rest_framework.response import Response
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView

from saude.models.diagnostico import Diagnostico
from saude.serializers.diagnostico import DiagnosticoSerializer


@registerView("diagnosticos")
class DiagnosticoAPIView(BaseAPIView):

    queryset = Diagnostico.objects.all()

    serializer_class = DiagnosticoSerializer



    # list_diagnostico: a plain @action had no permission (BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=False, methods=['GET'], url_path='consulta/(?P<consulta_id>[^/.]+)', label="Diagnoses of the consultation", permission="list_diagnostico", visible=False)
    def consulta(self, request, consulta_id=None):

        queryset = self.filter_queryset(
            self.get_queryset().filter(
                consulta_id=consulta_id
            )
        )

        serializer = self.get_serializer(
            queryset,
            many=True
        )

        return Response(serializer.data)