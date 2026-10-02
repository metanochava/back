# hr/views/shift.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.shift import Shift
from hr.serializers.shift import ShiftSerializer


@registerView('shifts', module='hr')
class ShiftAPIView(BaseAPIView):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer