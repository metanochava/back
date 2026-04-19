from django_resaas.core.base.serializers import BaseSerializer
from saude.models.examemedico import Examemedico
from rest_framework import serializers

class ExamemedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Examemedico
        fields = "__all__"
    