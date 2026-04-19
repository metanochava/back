from django_resaas.core.base.serializers import BaseSerializer
from saude.models.guiatransferencia import Guiatransferencia
from rest_framework import serializers

class GuiatransferenciaSerializer(BaseSerializer):
    
    class Meta:
        model = Guiatransferencia
        fields = "__all__"
    