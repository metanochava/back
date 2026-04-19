from django_resaas.core.base.serializers import BaseSerializer
from saude.models.tipoexamemedico import Tipoexamemedico
from rest_framework import serializers

class TipoexamemedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Tipoexamemedico
        fields = "__all__"
    