from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from rest_framework.decorators import action
from rest_framework.response import Response

from saude.models.episodioclinico import EpisodioClinico
from saude.serializers.episodioclinico import EpisodioClinicoSerializer


@registerView("episodiosclinicos")
class EpisodioClinicoAPIView(BaseAPIView):

    queryset = EpisodioClinico.objects.all()

    serializer_class = EpisodioClinicoSerializer


    from rest_framework.decorators import action
    from rest_framework.response import Response

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