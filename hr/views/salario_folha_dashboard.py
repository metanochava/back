from django.db.models import Avg, Sum
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.employee_salary import EmployeeSalary
from hr.models.payroll import Payroll
from hr.models.payroll_period import PayrollPeriod


@registerView("dashboard_salario_folha", module="hr")
class SalarioFolhaDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_salario_folha"

    def get(self, request, *args, **kwargs):
        periods_qs = self.apply_scope(request, PayrollPeriod.objects.all())
        open_periods_count = periods_qs.filter(is_closed=False).count()

        last_period = periods_qs.order_by("-end_date").first()
        last_period_total_cost = None
        if last_period:
            last_period_total_cost = (
                Payroll.objects
                .filter(period=last_period)
                .aggregate(total=Sum("net_salary"))["total"] or 0
            )

        salaries_qs = self.apply_scope(request, EmployeeSalary.objects.all())
        average_salary = (
            salaries_qs.filter(is_active=True).aggregate(avg=Avg("base_salary"))["avg"] or 0
        )

        return Response({
            "open_payroll_periods": open_periods_count,
            "last_period_name": getattr(last_period, "name", None),
            "last_period_total_net_cost": last_period_total_cost,
            "average_base_salary": average_salary,
        })
