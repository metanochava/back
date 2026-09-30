# hr/views/leave_balance_entry.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.leave_balance_entry import LeaveBalanceEntry
from hr.serializers.leave_balance_entry import LeaveBalanceEntrySerializer


@registerView('leavebalanceentries', module='hr')
class LeaveBalanceEntryAPIView(BaseAPIView):
    queryset = LeaveBalanceEntry.objects.all()
    serializer_class = LeaveBalanceEntrySerializer
