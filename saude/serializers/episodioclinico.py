from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.episodioclinico import EpisodioClinico


class EpisodioClinicoSerializer(BaseSerializer):

    class Meta:
        model = EpisodioClinico
        fields = "__all__"