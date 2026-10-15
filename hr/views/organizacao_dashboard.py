from datetime import timedelta
from django.db.models import Count
from django.utils import timezone
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.contract import Contract
from hr.models.contract_status import ContractStatus
from hr.models.employee import Employee
from hr.models.employee_specialty import EmployeeSpecialty


@registerView("dashboard_organizacao", module="hr")
class OrganizacaoDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_organizacao"

    def get(self, request, *args, **kwargs):
        employees_qs = self.apply_scope(request, Employee.objects.all())
        today = timezone.now().date()

        headcount_by_department = (
            employees_qs
            .values("position__department__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        contracts_qs = self.apply_scope(request, Contract.objects.all())
        contracts_expiring_soon = contracts_qs.filter(
            status=ContractStatus.ACTIVE,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=30),
        ).count()

        specialties_qs = self.apply_scope(request, EmployeeSpecialty.objects.all())
        by_specialty = (
            specialties_qs
            .values("specialty__title")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        return Response({
            "headcount_total": employees_qs.count(),
            "headcount_by_department": list(headcount_by_department),
            "contracts_expiring_soon": contracts_expiring_soon,
            "by_specialty": list(by_specialty),
        })
