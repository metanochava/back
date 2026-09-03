from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.classeexamemedico import ClasseExameMedico
from rest_framework import serializers
from django_resaas.engine.data.user.serializers.user import UserSerializer
from django_resaas.engine.models.user import User

class ClasseExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = ClasseExameMedico
        fields = "__all__"
    