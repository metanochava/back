from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView

from saude.models.procedimento import Procedimento
from saude.serializers.procedimento import ProcedimentoSerializer


from rest_framework.decorators import action
from rest_framework.response import Response


@registerView("procedimentos")
class ProcedimentoAPIView(BaseAPIView):

    queryset = Procedimento.objects.all()

    serializer_class = ProcedimentoSerializer


    @action(
        detail=False,
        methods=["GET"],
        url_path="consulta/(?P<consulta_id>[^/.]+)"
    )
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