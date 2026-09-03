from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.internamento import Internamento


class InternamentoSerializer(BaseSerializer):

    class Meta:
        model = Internamento
        fields = "__all__"
