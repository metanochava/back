from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from rest_framework.response import Response

from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView

from hr.models.application import Application
from hr.models.attendance import Attendance
from hr.models.contract import Contract, ContractStatus
from hr.models.employee_shift import EmployeeShift
from hr.models.disciplinary_case import DisciplinaryCase, DisciplinaryCaseStatus
from hr.models.employee import Employee
from hr.models.employee_goal import EmployeeGoal
from hr.models.employee_offboarding import EmployeeOffboarding, EmployeeOffboardingStatus
from hr.models.employee_onboarding import EmployeeOnboarding, EmployeeOnboardingStatus
from hr.models.employee_salary import EmployeeSalary
from hr.models.employee_specialty import EmployeeSpecialty
from hr.models.employee_training import EmployeeTraining
from hr.models.holiday import Holiday
from hr.models.interview import Interview
from hr.models.job_opening import JobOpening, JobOpeningStatus
from hr.models.leave_balance_entry import LeaveBalanceEntry
from hr.models.leave_request import LeaveRequest, LeaveRequestStatus
from hr.models.payroll import Payroll
from hr.models.payroll_period import PayrollPeriod
from hr.models.performance_cycle import PerformanceCycle, PerformanceCycleStatus
from hr.models.performance_review import PerformanceReview, ReviewStatus
from hr.models.promotion import Promotion
from hr.models.resignation import Resignation
from hr.models.termination import Termination
from hr.models.training_session import TrainingSession


# =========================================================
# 🏢 ORGANIZAÇÃO
# =========================================================

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


# =========================================================
# 🕒 TEMPO & PRESENÇA
# =========================================================

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


# =========================================================
# 💰 SALÁRIO & FOLHA DE PAGAMENTO
# =========================================================

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


# =========================================================
# 🏖️ AUSÊNCIAS
# =========================================================

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


# =========================================================
# 🧑‍💼 RECRUTAMENTO
# =========================================================

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


# =========================================================
# 📋 ONBOARDING
# =========================================================

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


# =========================================================
# 📈 DESEMPENHO
# =========================================================

@registerView("dashboard_desempenho", module="hr")
class DesempenhoDashboardAPIView(TenantDashboardAPIView):
    module_name = "hr"
    permission_codename = "view_dashboard_hr_desempenho"

    def get(self, request, *args, **kwargs):
        cycles_qs = self.apply_scope(request, PerformanceCycle.objects.all())
        active_cycle = cycles_qs.filter(status=PerformanceCycleStatus.ACTIVE).first()

        reviews_qs = self.apply_scope(request, PerformanceReview.objects.all())
        pending_reviews = reviews_qs.filter(status=ReviewStatus.DRAFT).count()

        goals_qs = self.apply_scope(request, EmployeeGoal.objects.all())
        goals_by_status = (
            goals_qs
            .values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )

        return Response({
            "active_cycle": (
                {"id": active_cycle.id, "name": active_cycle.name}
                if active_cycle else None
            ),
            "pending_reviews": pending_reviews,
            "goals_by_status": list(goals_by_status),
        })


# =========================================================
# 🎓 FORMAÇÃO
# =========================================================

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


# =========================================================
# 🔄 CICLO DE VIDA DO COLABORADOR
# =========================================================

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
