# hr/views/employee_goal.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_goal import EmployeeGoal
from hr.serializers.employee_goal import EmployeeGoalSerializer
from hr.services import performance_service
from django_resaas.saas.core.exceptions.handler import error_response


@registerView('employeegoals', module='hr')
class EmployeeGoalAPIView(BaseAPIView):
    queryset = EmployeeGoal.objects.all()
    serializer_class = EmployeeGoalSerializer

    # get_object() already scopes to the caller's tenant.

    @resaas_action(detail=True, methods=["post"])
    def update_progress(self, request, *args, **kwargs):
        goal = self.get_object()

        progress = request.data.get("progress")
        new_status = request.data.get("status")

        if progress is None:
            return error_response(request, "progress is required.", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            progress = int(progress)
        except (TypeError, ValueError):
            return error_response(request, "progress must be an integer.", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                performance_service.update_goal_progress(
                    goal, progress=progress, status=new_status, actor=request.user,
                )
        except performance_service.PerformanceError as exc:
            return error_response(request, str(exc), status_code=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeGoalSerializer(goal, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
