# hr/views/employee_offboarding_task.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.employee_offboarding_task import EmployeeOffboardingTask
from hr.serializers.employee_offboarding_task import (
    EmployeeOffboardingTaskSerializer,
)
from hr.services import lifecycle_service


@registerView('employeeoffboardingtasks', module='hr')
class EmployeeOffboardingTaskAPIView(BaseAPIView):
    queryset = EmployeeOffboardingTask.objects.all()
    serializer_class = EmployeeOffboardingTaskSerializer

    @resaas_action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        task = self.get_object()
        notes = request.data.get("notes") or ""

        try:
            with transaction.atomic():
                lifecycle_service.complete_offboarding_task(task, actor=request.user, notes=notes)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOffboardingTaskSerializer(task, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def reopen(self, request, *args, **kwargs):
        task = self.get_object()

        try:
            with transaction.atomic():
                lifecycle_service.reopen_offboarding_task(task, actor=request.user)
        except lifecycle_service.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeOffboardingTaskSerializer(task, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
