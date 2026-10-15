from django.db.models import Sum
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.leave_balance_entry import LeaveBalanceEntry
from hr.models.leave_request import LeaveRequest
from hr.models.leave_request_status import LeaveRequestStatus


@registerView("dashboard_ausencias", module="hr")
class AusenciasDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_ausencias"

    def get(self, request, *args, **kwargs):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        leave_qs = self.apply_scope(request, LeaveRequest.objects.all())

        pending_approvals = leave_qs.filter(status=LeaveRequestStatus.PENDING).count()
        this_month_count = leave_qs.filter(start_date__gte=month_start).count()

        balance_qs = self.apply_scope(request, LeaveBalanceEntry.objects.all())
        lowest_balances = (
            balance_qs
            .values("employee_id", "employee__person__full_name")
            .annotate(balance=Sum("amount"))
            .order_by("balance")[:10]
        )

        return Response({
            "pending_approvals": pending_approvals,
            "leave_requests_this_month": this_month_count,
            "lowest_balances": list(lowest_balances),
        })
