from django_resaas.engine.core.base.serializers import BaseSerializer
from saude.models.emergency_access import EmergencyAccess


class EmergencyAccessSerializer(BaseSerializer):

    class Meta:
        model = EmergencyAccess
        fields = "__all__"
