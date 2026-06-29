from django_resaas.core.base.serializers import BaseSerializer
from saude.models.classeexamemedico import ClasseExameMedico
from rest_framework import serializers
from django_resaas.data.user.serializers.user import UserSerializer
from django_resaas.models.user import User

class ClasseExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = ClasseExameMedico
        fields = "__all__"
    