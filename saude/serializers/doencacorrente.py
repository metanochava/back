from django_resaas.core.base.serializers import BaseSerializer
from saude.models.doencacorrente import Doencacorrente
from rest_framework import serializers

class DoencacorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = Doencacorrente
        fields = "__all__"
    