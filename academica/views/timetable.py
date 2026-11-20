"""The classes' timetables and the schooling students bring from other
institutions (PROTECTED, BaseAPIView: per action permission, the Entity /
Branch scope).

    GET academica/timetableslots/week/?class_group=&teacher=&room=&academic_year=
    GET academica/timetableslots/mine/?enrolment=   the portal: the caller's own class
"""
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica import models as m
from academica import serializers as s
from academica.services import portal_service, timetable_service
from academica.views._conflict import UniqueConflictMixin


@registerView("timetableslots")
class TimetableSlotAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.TimetableSlot.objects.select_related("subject", "class_group", "teacher__person")
    serializer_class = s.TimetableSlotSerializer

    @resaas_action(detail=False, methods=["get"], label="Week", icon="calendar_view_week",
                   permission="list_timetableslot", visible=False)
    def week(self, request):
        q = request.query_params
        return Response(timetable_service.week(
            self.filter_queryset(self.get_queryset()), class_group_id=q.get("class_group") or None,
            teacher_id=q.get("teacher") or None, room_id=q.get("room") or None,
            academic_year_id=q.get("academic_year") or None,
        ))

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My timetable", icon="calendar_view_week",
                   permission="view_own_enrolment", visible=False)
    def view_own(self, request):
        """?enrolment=<one of the caller's own>: that class's week."""
        if not request.query_params.get("enrolment"):
            raise ResaasAPIException("Choose an enrolment.", code="invalid",
                                     details={"enrolment": ["Choose an enrolment."]})
        enrolment = portal_service.own_enrolment(request, request.query_params.get("enrolment"))
        return Response(timetable_service.for_enrolment(enrolment))


@registerView("priorschoolings")
class PriorSchoolingAPIView(UniqueConflictMixin, BaseAPIView):
    queryset = m.PriorSchooling.objects.select_related("student__person")
    serializer_class = s.PriorSchoolingSerializer
