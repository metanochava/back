from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.employee_training import EmployeeTraining
from hr.models.training_session import TrainingSession


@registerView("dashboard_formacao", module="hr")
class FormacaoDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_formacao"

    def get(self, request, *args, **kwargs):
        now = timezone.now()

        sessions_qs = self.apply_scope(request, TrainingSession.objects.all())
        upcoming_sessions = sessions_qs.filter(
            start_date__gte=now,
            start_date__lte=now + timedelta(days=30),
        )

        enrollments_qs = self.apply_scope(request, EmployeeTraining.objects.all())
        upcoming_enrollments = enrollments_qs.filter(
            session__in=upcoming_sessions
        ).count()

        return Response({
            "upcoming_sessions_count": upcoming_sessions.count(),
            "upcoming_sessions_enrollments": upcoming_enrollments,
        })
