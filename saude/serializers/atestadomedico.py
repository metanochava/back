from django_resaas.core.base.serializers import BaseSerializer
from saude.models.atestadomedico import Atestadomedico
from rest_framework import serializers

class AtestadomedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Atestadomedico
        fields = "__all__"
    