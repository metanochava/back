# hr/views/transfer.py

from rest_framework.response import Response
from rest_framework import status

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.transfer import Transfer
from hr.serializers.transfer import TransferSerializer


@registerView('transfers', module='hr')
class TransferAPIView(BaseAPIView):
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer

    # Creation is exclusively through EmployeeAPIView.apply_transfer (it
    # needs to also update Employee.branch/position and validate the
    # destination is in the same Entity in the same transaction - see
    # lifecycle_service.apply_transfer).
    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /hr/employees/{id}/apply_transfer/ instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
