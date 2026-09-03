from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.tipoexamemedico import TipoExameMedico
from rest_framework import serializers

class TipoExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = TipoExameMedico
        fields = "__all__"
    