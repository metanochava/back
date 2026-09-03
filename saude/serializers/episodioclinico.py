from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.episodioclinico import EpisodioClinico


class EpisodioClinicoSerializer(BaseSerializer):

    class Meta:
        model = EpisodioClinico
        fields = "__all__"