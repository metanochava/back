from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from saude.models.appointment_request import AppointmentRequest
from saude.serializers.appointment_request import AppointmentRequestSerializer
from saude.services import public_booking_service


@registerView("appointmentrequests")
class AppointmentRequestAPIView(BaseAPIView):
    """Staff: appointment requests made on the public site (Entity + Branch
    scope of the signed context - the Branch of the doctor's schedule).

    Created only by the public site (saude/publicbooking/requests/): POST
    here is 405. A request is handled through its actions:

        POST appointmentrequests/{id}/confirm/  {paciente}  -> creates the Agenda
        POST appointmentrequests/{id}/reject/   {reason?}
    """

    queryset = AppointmentRequest.objects.select_related("medico__person", "agenda")
    serializer_class = AppointmentRequestSerializer

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    @resaas_action(methods=["post"], detail=True, label="Confirm", icon="event_available")
    def confirm(self, request, *args, **kwargs):
        appointment_request = public_booking_service.confirm(
            self.get_object(), request.data.get("paciente"), request.user
        )
        return Response(self.get_serializer(appointment_request).data)

    @resaas_action(methods=["post"], detail=True, label="Reject", icon="event_busy")
    def reject(self, request, *args, **kwargs):
        appointment_request = public_booking_service.reject(
            self.get_object(), request.data.get("reason"), request.user
        )
        return Response(self.get_serializer(appointment_request).data)
