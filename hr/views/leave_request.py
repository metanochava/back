# hr/views/leave_request.py

from django.db import transaction
from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action

from hr.models.leave_request import LeaveRequest
from hr.serializers.leave_request import LeaveRequestSerializer
from hr.services import leave_service


@registerView('leaverequests', module='hr')
class LeaveRequestAPIView(BaseAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer

    # get_object() already scopes to the caller's tenant (get_queryset()
    # filters by entity_id/branch_id - see BaseAPIView), so an Entity can
    # never submit/approve/reject/cancel a LeaveRequest it can't already
    # see - same guarantee check_in/check_out on EmployeeAPIView rely on
    # (Fase 2).

    @resaas_action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs):
        leave_request = self.get_object()

        try:
            with transaction.atomic():
                leave_service.submit(leave_request, actor=request.user)
        except leave_service.LeaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveRequestSerializer(leave_request, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def approve(self, request, *args, **kwargs):
        leave_request = self.get_object()

        try:
            with transaction.atomic():
                leave_service.approve(leave_request, actor=request.user)
        except leave_service.LeaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveRequestSerializer(leave_request, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def reject(self, request, *args, **kwargs):
        leave_request = self.get_object()
        reason = request.data.get("rejection_reason") or request.data.get("reason")

        try:
            with transaction.atomic():
                leave_service.reject(leave_request, actor=request.user, reason=reason)
        except leave_service.LeaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveRequestSerializer(leave_request, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @resaas_action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        leave_request = self.get_object()

        try:
            with transaction.atomic():
                leave_service.cancel(leave_request, actor=request.user)
        except leave_service.LeaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            LeaveRequestSerializer(leave_request, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
