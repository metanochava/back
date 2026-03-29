from django_resaas.core.base.serializers import BaseSerializer
from clinica.models.receita_medica import ReceitaMedica
from rest_framework import serializers

class ReceitaMedicaSerializer(BaseSerializer):
    
    class Meta:
        model = ReceitaMedica
        fields = "__all__"
    