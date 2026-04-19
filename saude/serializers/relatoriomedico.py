from django_resaas.core.base.serializers import BaseSerializer
from saude.models.relatoriomedico import Relatoriomedico
from rest_framework import serializers

class RelatoriomedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Relatoriomedico
        fields = "__all__"
    