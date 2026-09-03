from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.medicacaocorrente import MedicacaoCorrente
from rest_framework import serializers

class MedicacaoCorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = MedicacaoCorrente
        fields = "__all__"
    