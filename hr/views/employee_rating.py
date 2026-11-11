# hr/views/employee_rating.py

from django.db import transaction
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_rating import EmployeeRating
from hr.serializers.employee_rating import EmployeeRatingSerializer
from hr.services import employee_rating_service


@registerView('employeeratings', module='hr')
class EmployeeRatingAPIView(BaseAPIView):
    """PROTECTED. The ratings of this Entity's employees, for whoever
    moderates their comments (list/view_employeerating,
    moderate_employeerating). Never created or edited here: a rating comes
    from the rated service (saude: the patient portal, a completed
    appointment) and only its comment is moderated."""

    queryset = EmployeeRating.objects.select_related("employee__person")
    serializer_class = EmployeeRatingSerializer
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    @resaas_action(detail=True, methods=["post"], label="Moderate comment", icon="fact_check", visible=False)
    @transaction.atomic
    def moderate(self, request, *args, **kwargs):
        """body {status: approved|rejected}"""
        rating = self.get_object()
        employee_rating_service.moderate(rating, request.data.get("status"), request.user)
        return Response(self.get_serializer(rating).data)
