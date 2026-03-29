# rh/api/serializers/Cargo.py

from django_resaas.core.base.serializers import BaseSerializer
from rh.models.cargo import Cargo

class CargoSerializer(BaseSerializer):
    class Meta:
        model = Cargo
        fields = "__all__"