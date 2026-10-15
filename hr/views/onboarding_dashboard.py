from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.employee_onboarding import EmployeeOnboarding
from hr.models.employee_onboarding_status import EmployeeOnboardingStatus


@registerView("dashboard_onboarding", module="hr")
class OnboardingDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_onboarding"

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        onboarding_qs = self.apply_scope(request, EmployeeOnboarding.objects.all())

        in_progress = onboarding_qs.filter(
            status=EmployeeOnboardingStatus.IN_PROGRESS
        ).count()
        completed_this_month = onboarding_qs.filter(
            status=EmployeeOnboardingStatus.COMPLETED,
            completed_at__gte=month_start,
        ).count()

        return Response({
            "onboardings_in_progress": in_progress,
            "onboardings_completed_this_month": completed_this_month,
        })
