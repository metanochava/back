# hr/views/training_session.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.training_session import TrainingSession
from hr.models.employee import Employee
from hr.serializers.training_session import TrainingSessionSerializer
from hr.serializers.employee_training import EmployeeTrainingSerializer
from hr.services import training_service


@registerView('trainingsessions', module='hr')
class TrainingSessionAPIView(BaseAPIView):
    queryset = TrainingSession.objects.all()
    serializer_class = TrainingSessionSerializer

    # get_object() already scopes to the caller's tenant.

    @resaas_action(detail=True, methods=["post"])
    def enroll(self, request, *args, **kwargs):
        session = self.get_object()

        employee_id = request.data.get("employee")

        if not employee_id:
            return Response(
                {"detail": "employee is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Looked up scoped to the session's own entity, not the generic
        # (tenant-filtered-by-context) queryset - the employee id comes
        # straight from the request body, so this is the check that keeps
        # Entity A from enrolling an Entity B employee (pedido secção 103).
        try:
            employee = Employee.objects.get(id=employee_id, entity_id=session.entity_id)
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                enrollment = training_service.enroll(session, employee, actor=request.user)
        except training_service.TrainingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EmployeeTrainingSerializer(enrollment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @resaas_action(detail=True, methods=["post"])
    def cancel_session(self, request, *args, **kwargs):
        session = self.get_object()

        try:
            with transaction.atomic():
                training_service.cancel_session(session, actor=request.user)
        except training_service.TrainingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TrainingSessionSerializer(session, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
