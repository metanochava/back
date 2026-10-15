from django.db.models import Count
from rest_framework.response import Response
from django_resaas.saas.core.base.dashboard import TenantDashboardAPIView
from django_resaas.saas.core.base.views import registerView
from hr.models.employee_goal import EmployeeGoal
from hr.models.performance_cycle import PerformanceCycle
from hr.models.performance_cycle_status import PerformanceCycleStatus
from hr.models.performance_review import PerformanceReview
from hr.models.review_status import ReviewStatus


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
