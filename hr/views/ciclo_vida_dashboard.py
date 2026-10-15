from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.disciplinary_case import DisciplinaryCase
from hr.models.disciplinary_case_status import DisciplinaryCaseStatus
from hr.models.employee_offboarding import EmployeeOffboarding
from hr.models.employee_offboarding_status import EmployeeOffboardingStatus
from hr.models.promotion import Promotion
from hr.models.resignation import Resignation
from hr.models.termination import Termination


@registerView("dashboard_ciclo_vida", module="hr")
class CicloVidaDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_ciclo_vida"

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        month_start = now.date().replace(day=1)

        promotions_qs = self.apply_scope(request, Promotion.objects.all())
        promotions_this_period = promotions_qs.filter(
            effective_date__gte=month_start
        ).count()

        terminations_qs = self.apply_scope(request, Termination.objects.all())
        terminations_this_period = terminations_qs.filter(
            termination_date__gte=month_start
        ).count()

        resignations_qs = self.apply_scope(request, Resignation.objects.all())
        resignations_this_period = resignations_qs.filter(
            resignation_date__gte=month_start
        ).count()

        cases_qs = self.apply_scope(request, DisciplinaryCase.objects.all())
        active_cases = cases_qs.filter(
            status__in=[DisciplinaryCaseStatus.OPEN, DisciplinaryCaseStatus.UNDER_REVIEW]
        ).count()

        offboarding_qs = self.apply_scope(request, EmployeeOffboarding.objects.all())
        offboarding_in_progress = offboarding_qs.filter(
            status=EmployeeOffboardingStatus.IN_PROGRESS
        ).count()

        return Response({
            "promotions_this_period": promotions_this_period,
            "terminations_this_period": terminations_this_period,
            "resignations_this_period": resignations_this_period,
            "active_disciplinary_cases": active_cases,
            "offboarding_in_progress": offboarding_in_progress,
        })
