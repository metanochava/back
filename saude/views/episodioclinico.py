from django_resaas.saas.core.base.views import BaseAPIView
from django_resaas.saas.core.base.views import registerView
from rest_framework.decorators import action
from django_resaas.saas.core.decorators.action import resaas_action
from rest_framework.response import Response

from saude.models.episodioclinico import EpisodioClinico
from saude.serializers.episodioclinico import EpisodioClinicoSerializer


@registerView("episodiosclinicos")
class EpisodioClinicoAPIView(BaseAPIView):

    queryset = EpisodioClinico.objects.all()

    serializer_class = EpisodioClinicoSerializer


    from rest_framework.decorators import action
    from rest_framework.response import Response

    # list_episodioclinico: a plain @action had no permission (BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=False, methods=['GET'], url_path='consulta/(?P<consulta_id>[^/.]+)', label="Clinical episodes of the consultation", permission="list_episodioclinico", visible=False)
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