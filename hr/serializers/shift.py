# hr/serializers/shift.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.shift import Shift


class ShiftSerializer(BaseSerializer):

    class Meta:
        model = Shift
        fields = "__all__"