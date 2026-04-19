from django_resaas.core.base.serializers import BaseSerializer
from saude.models.classeexamemedico import Classeexamemedico
from rest_framework import serializers

class ClasseexamemedicoSerializer(BaseSerializer):
    
    class Meta:
        model = Classeexamemedico
        fields = "__all__"
    