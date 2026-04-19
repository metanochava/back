from django_resaas.core.base.serializers import BaseSerializer
from saude.models.medicamento import Medicamento
from rest_framework import serializers

class MedicamentoSerializer(BaseSerializer):
    
    class Meta:
        model = Medicamento
        fields = "__all__"
    