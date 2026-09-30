# hr/views/holiday.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.holiday import Holiday
from hr.serializers.holiday import HolidaySerializer


@registerView('holidays', module='hr')
class HolidayAPIView(BaseAPIView):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
