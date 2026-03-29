from django_resaas.core.base.serializers import BaseSerializer
from clinica.models.seguradora import Seguradora
from rest_framework import serializers

class SeguradoraSerializer(BaseSerializer):
    
    class Meta:
        model = Seguradora
        fields = "__all__"
    