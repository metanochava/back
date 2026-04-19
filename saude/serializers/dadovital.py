from django_resaas.core.base.serializers import BaseSerializer
from saude.models.dadovital import Dadovital
from rest_framework import serializers

class DadovitalSerializer(BaseSerializer):
    
    class Meta:
        model = Dadovital
        fields = "__all__"
    