from django_resaas.core.base.serializers import BaseSerializer
from clinica.models.alergia_corrente import AlergiaCorrente
from rest_framework import serializers

class AlergiaCorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = AlergiaCorrente
        fields = "__all__"
    