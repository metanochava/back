# rh/api/serializers/Departamento.py

from django_resaas.core.base.serializers import BaseSerializer
from rh.models.departamento import Departamento

class DepartamentoSerializer(BaseSerializer):
    class Meta:
        model = Departamento
        fields = "__all__"