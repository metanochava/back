from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.attendance import Attendance
from hr.models.employee_shift import EmployeeShift
from hr.models.holiday import Holiday


@registerView("dashboard_tempo_presenca", module="hr")
class TempoPresencaDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_tempo_presenca"

    def get(self, request, *args, **kwargs):
        today = timezone.now().date()

        attendance_qs = self.apply_scope(request, Attendance.objects.all())
        today_attendance = attendance_qs.filter(date=today).count()

        active_shifts_qs = self.apply_scope(request, EmployeeShift.objects.all())
        employees_on_shift_today = active_shifts_qs.filter(
            is_active=True,
            start_date__lte=today,
        ).exclude(end_date__lt=today).count()

        holidays_qs = self.apply_scope(request, Holiday.objects.all())
        upcoming_holidays = list(
            holidays_qs
            .filter(date__gte=today, date__lte=today + timedelta(days=30))
            .order_by("date")
            .values("id", "name", "date")[:10]
        )

        return Response({
            "today_attendance_count": today_attendance,
            "employees_on_shift_today": employees_on_shift_today,
            "upcoming_holidays": upcoming_holidays,
        })
