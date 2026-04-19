from django_resaas.core.base.serializers import BaseSerializer
from saude.models.receitamedica import Receitamedica
from rest_framework import serializers

class ReceitamedicaSerializer(BaseSerializer):
    
    class Meta:
        model = Receitamedica
        fields = "__all__"
    