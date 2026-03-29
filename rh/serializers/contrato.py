# rh/api/serializers/Contrato.py

from django_resaas.core.base.serializers import BaseSerializer
from rh.models.contrato import Contrato

class ContratoSerializer(BaseSerializer):
    class Meta:
        model = Contrato
        fields = "__all__"