from django_resaas.core.base.serializers import BaseSerializer
from rh.models.departamento import Departamento
from rest_framework import serializers
from django_resaas.models.user import User
from django_resaas.data.user.serializers.user import UserSerializer

class DepartamentoSerializer(BaseSerializer):
        
    gestor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), write_only=True
    )
    gestor_data = UserSerializer(read_only=True)

    class Meta:
        model = Departamento
        fields = "__all__"
    