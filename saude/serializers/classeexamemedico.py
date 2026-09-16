from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.classeexamemedico import ClasseExameMedico
from rest_framework import serializers
from django_resaas.saas.data.user.serializers.user import UserSerializer
from django_resaas.saas.models.user import User

class ClasseExameMedicoSerializer(BaseSerializer):
    
    class Meta:
        model = ClasseExameMedico
        fields = "__all__"
    