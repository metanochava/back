# rh/api/serializers/funcionario_cargo.py

from django_resaas.core.base.serializers import BaseSerializer
from rh.models.funcionario_cargo import FuncionarioCargo

class FuncionarioCargoSerializer(BaseSerializer):
    class Meta:
        model = FuncionarioCargo
        fields = "__all__"