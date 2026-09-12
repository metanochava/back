from django_resaas.saas.core.base.serializers import BaseSerializer
from saude.models.emergency_access import EmergencyAccess


class EmergencyAccessSerializer(BaseSerializer):

    class Meta:
        model = EmergencyAccess
        fields = "__all__"
