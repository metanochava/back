from django_resaas.core.base.serializers import BaseSerializer
from saude.models.medicacaocorrente import Medicacaocorrente
from rest_framework import serializers

class MedicacaocorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = Medicacaocorrente
        fields = "__all__"
    