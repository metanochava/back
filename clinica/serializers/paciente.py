from django_resaas.core.base.serializers import BaseSerializer
from clinica.models.paciente import Paciente
from rest_framework import serializers

class PacienteSerializer(BaseSerializer):
    
    class Meta:
        model = Paciente
        fields = "__all__"
    