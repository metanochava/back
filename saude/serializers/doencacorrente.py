from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.doencacorrente import DoencaCorrente
from rest_framework import serializers

class DoencaCorrenteSerializer(BaseSerializer):
    
    class Meta:
        model = DoencaCorrente
        fields = "__all__"
    