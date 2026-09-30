# hr/serializers/holiday.py

from django_resaas.saas.core.base.serializers import BaseSerializer

from hr.models.holiday import Holiday


class HolidaySerializer(BaseSerializer):

    class Meta:
        model = Holiday
        fields = "__all__"
