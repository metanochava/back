from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.application import Application
from hr.models.interview import Interview
from hr.models.job_opening import JobOpening
from hr.models.job_opening_status import JobOpeningStatus


@registerView("dashboard_recrutamento", module="hr")
class RecrutamentoDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_recrutamento"

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        openings_qs = self.apply_scope(request, JobOpening.objects.all())
        open_openings = openings_qs.filter(status=JobOpeningStatus.OPEN).count()

        applications_qs = self.apply_scope(request, Application.objects.all())
        applications_this_month = applications_qs.filter(created_at__gte=month_start).count()

        interviews_qs = self.apply_scope(request, Interview.objects.all())
        upcoming_interviews = interviews_qs.filter(
            scheduled_at__gte=now,
            scheduled_at__lte=now + timedelta(days=7),
        ).count()

        return Response({
            "open_job_openings": open_openings,
            "applications_this_month": applications_this_month,
            "upcoming_interviews": upcoming_interviews,
        })
