"""Providers dos widgets de hr/dashboard.py - mesmas queries já usadas
pelo mecanismo antigo (views/dashboard.py's Organizacao/TempoPresenca/
SalarioFolha/Ausencias APIViews), reorganizadas como widgets
individuais do motor novo (saas/core/dashboards/). Um subconjunto
representativo, não uma migração 1:1 de todas as 8 secções antigas -
cada secção antiga continua a funcionar como estava."""

from django.utils import timezone
from datetime import timedelta

from django_resaas.saas.core.dashboards.providers import (
    BaseDashboardProvider,
    register_provider,
)

from hr.models.attendance import Attendance
from hr.models.employee import Employee
from hr.models.holiday import Holiday
from hr.models.leave_request import LeaveRequest, LeaveRequestStatus
from hr.models.payroll_period import PayrollPeriod


@register_provider("hr.headcount_total")
class HeadcountTotalProvider(BaseDashboardProvider):

    def resolve(self):
        value = self.scoped_queryset(Employee.objects.all()).count()

        return {
            "value": value,
            "formatted_value": str(value),
        }


@register_provider("hr.pending_leave_approvals")
class PendingLeaveApprovalsProvider(BaseDashboardProvider):

    def resolve(self):
        qs = self.scoped_queryset(LeaveRequest.objects.all())
        value = qs.filter(status=LeaveRequestStatus.PENDING).count()

        return {
            "value": value,
            "formatted_value": str(value),
        }


@register_provider("hr.today_attendance")
class TodayAttendanceProvider(BaseDashboardProvider):

    def resolve(self):
        today = timezone.now().date()
        qs = self.scoped_queryset(Attendance.objects.all())
        value = qs.filter(date=today).count()

        return {
            "value": value,
            "formatted_value": str(value),
        }


@register_provider("hr.open_payroll_periods")
class OpenPayrollPeriodsProvider(BaseDashboardProvider):

    def resolve(self):
        qs = self.scoped_queryset(PayrollPeriod.objects.all())
        value = qs.filter(is_closed=False).count()

        return {
            "value": value,
            "formatted_value": str(value),
        }


@register_provider("hr.upcoming_holidays")
class UpcomingHolidaysProvider(BaseDashboardProvider):

    def resolve(self):
        today = timezone.now().date()
        qs = self.scoped_queryset(Holiday.objects.all())

        rows = list(
            qs
            .filter(date__gte=today, date__lte=today + timedelta(days=30))
            .order_by("date")
            .values("id", "name", "date")[:10]
        )

        return {
            "columns": [
                {"name": "name", "label": "Feriado"},
                {"name": "date", "label": "Data"},
            ],
            "rows": rows,
            "pagination": {
                "count": len(rows),
                "next": False,
                "previous": False,
            },
        }
