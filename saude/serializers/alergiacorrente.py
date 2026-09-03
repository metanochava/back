from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.alergiacorrente import AlergiaCorrente
from rest_framework import serializers

class AlergiaCorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = AlergiaCorrente
        fields = "__all__"
    