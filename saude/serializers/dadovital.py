from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.dadovital import DadoVital
from rest_framework import serializers

class DadoVitalSerializer(BaseSerializer):
    
    class Meta:
        model = DadoVital
        fields = "__all__"
    