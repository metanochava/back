from django_resaas.core.base.serializers import BaseSerializer
from saude.models.consulta import Consulta
from rest_framework import serializers

class ConsultaSerializer(BaseSerializer):
    
    class Meta:
        model = Consulta
        fields = "__all__"
    