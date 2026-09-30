# hr/views/termination.py

from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.termination import Termination
from hr.serializers.termination import TerminationSerializer


@registerView('terminations', module='hr')
class TerminationAPIView(BaseAPIView):
    queryset = Termination.objects.all()
    serializer_class = TerminationSerializer

    # Creation is exclusively through EmployeeAPIView.terminate_employee -
    # see lifecycle_service.terminate_employee.
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/employees/{id}/terminate_employee/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
