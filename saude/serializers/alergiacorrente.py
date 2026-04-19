from django_resaas.core.base.serializers import BaseSerializer
from saude.models.alergiacorrente import Alergiacorrente
from rest_framework import serializers

class AlergiacorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = Alergiacorrente
        fields = "__all__"
    