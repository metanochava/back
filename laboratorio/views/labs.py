"""The laboratorio API (PROTECTED, BaseAPIView: per action permission, the
Entity / Branch scope).

Staff: CRUD of rooms, networks, workstations, equipment, environments,
sessions, seats and exercises; sessions start / end / cancel; remote
access - POST labsessions/{id}/remote_access/ {seat, reason, minutes?} opens
it (the session's teacher, while running), POST remoteaccesses/{id}/end/
ends it; remoteaccesses/ is read-only (the audit trail).

Students and guardians: GET labsessions/mine/?enrolment=<own> - the class's
sessions with the student's seat, exercises and any active remote access on
that seat (never hidden from them).
"""
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica.services import portal_service
from laboratorio import models as m
from laboratorio import serializers as s
from laboratorio.services import remote_access_service, session_service


class _Base(BaseAPIView):
    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                super().perform_create(serializer)
        except IntegrityError:
            raise ResaasAPIException("This record already exists.", code="already_exists", status_code=409)

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                super().perform_update(serializer)
        except IntegrityError:
            raise ResaasAPIException("This record already exists.", code="already_exists", status_code=409)


def _teacher(request):
    from pedagogica.services.assignment_service import teacher_of

    return teacher_of(request)


@registerView("rooms")
class RoomAPIView(_Base):
    queryset = m.Room.objects.all()
    serializer_class = s.RoomSerializer


@registerView("networks")
class NetworkAPIView(_Base):
    queryset = m.Network.objects.select_related("room")
    serializer_class = s.NetworkSerializer


@registerView("workstations")
class WorkstationAPIView(_Base):
    queryset = m.Workstation.objects.select_related("room", "network")
    serializer_class = s.WorkstationSerializer


@registerView("equipment")
class EquipmentAPIView(_Base):
    queryset = m.Equipment.objects.select_related("room")
    serializer_class = s.EquipmentSerializer


@registerView("environments")
class EnvironmentAPIView(_Base):
    queryset = m.Environment.objects.all()
    serializer_class = s.EnvironmentSerializer


@registerView("labsessions")
class LabSessionAPIView(_Base):
    queryset = m.LabSession.objects.select_related("room", "class_group", "subject", "teacher__person", "environment")
    serializer_class = s.LabSessionSerializer

    def perform_create(self, serializer):
        if not serializer.validated_data.get("teacher"):
            teacher = _teacher(self.request)
            if teacher is None:
                raise ResaasAPIException("Choose the session's teacher.", code="invalid",
                                         details={"teacher": ["Choose the session's teacher."]})
            serializer.validated_data["teacher"] = teacher
        super().perform_create(serializer)

    def _move(self, request, fn):
        return Response(self.get_serializer(fn(session=self.get_object(), user=request.user, request=request)).data)

    @resaas_action(detail=True, methods=["post"], label="Start", icon="play_arrow")
    def start(self, request, pk=None):
        return self._move(request, session_service.start)

    @resaas_action(detail=True, methods=["post"], label="End", icon="stop")
    def end(self, request, pk=None):
        return self._move(request, session_service.end)

    @resaas_action(detail=True, methods=["post"], label="Cancel", icon="cancel")
    def cancel(self, request, pk=None):
        return self._move(request, session_service.cancel)

    @resaas_action(detail=True, methods=["get"], label="Seats", icon="event_seat", permission="list_seatassignment",
                   visible=False)
    def seats(self, request, pk=None):
        session = self.get_object()
        remote_access_service.expire_due(m.RemoteAccessSession.objects.filter(session=session))
        active = {str(a.seat_id): s.RemoteAccessSerializer(a, context={"request": request}).data
                  for a in session.remote_accesses.filter(status=m.RemoteAccessSession.STATUS_ACTIVE)}
        rows = session.seats.select_related("enrolment__student__person", "workstation")
        return Response([{**s.SeatAssignmentSerializer(seat, context={"request": request}).data,
                          "student": seat.enrolment.student.person.full_name,
                          "workstation_code": seat.workstation.code,
                          "remote_access": active.get(str(seat.id))} for seat in rows])

    @resaas_action(detail=True, methods=["post"], label="Remote access", icon="screen_share",
                   permission="start_remoteaccesssession", visible=False)
    def remote_access(self, request, pk=None):
        """{seat, reason, minutes?}: the session's teacher, while it runs."""
        session = self.get_object()
        seat = session.seats.filter(id=request.data.get("seat")).select_related("workstation", "session").first() \
            if request.data.get("seat") else None
        if seat is None:
            raise ResaasAPIException("Choose a seat of this session.", code="invalid",
                                     details={"seat": ["Choose a seat of this session."]})
        access = remote_access_service.start(seat=seat, teacher=_teacher(request), reason=request.data.get("reason"),
                                             minutes=request.data.get("minutes"), user=request.user, request=request)
        return Response(s.RemoteAccessSerializer(access, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My lab sessions", icon="computer",
                   permission="view_own_labsession", visible=False)
    def view_own(self, request):
        """?enrolment=<own>: the class's sessions (newest first) with the
        student's seat, the exercises and an active remote access, if any."""
        enrolment = portal_service.own_enrolment(request, request.query_params.get("enrolment"))
        sessions = (m.LabSession.objects.filter(entity_id=enrolment.entity_id, class_group_id=enrolment.class_group_id)
                    .exclude(status=m.LabSession.STATUS_CANCELLED)
                    .select_related("room", "subject", "teacher__person").order_by("-starts_at")[:100])
        remote_access_service.expire_due(m.RemoteAccessSession.objects.filter(seat__enrolment=enrolment))
        rows = []
        for session in sessions:
            seat = session.seats.filter(enrolment=enrolment).select_related("workstation").first()
            access = seat.remote_accesses.filter(status=m.RemoteAccessSession.STATUS_ACTIVE).first() if seat else None
            rows.append({
                "id": str(session.id), "title": session.title, "status": session.status,
                "starts_at": session.starts_at, "ends_at": session.ends_at,
                "room": session.room.name, "subject": session.subject.name,
                "teacher": session.teacher.person.full_name,
                "workstation": seat.workstation.code if seat else None,
                "exercises": [{"id": str(e.assignment_id), "title": e.assignment.title}
                              for e in session.exercises.select_related("assignment")],
                "remote_access": {"teacher": access.teacher.person.full_name, "reason": access.reason,
                                  "started_at": access.started_at, "expires_at": access.expires_at} if access else None,
            })
        return Response(rows)


@registerView("seatassignments")
class SeatAssignmentAPIView(_Base):
    queryset = m.SeatAssignment.objects.select_related("session", "enrolment__student__person", "workstation")
    serializer_class = s.SeatAssignmentSerializer


@registerView("sessionexercises")
class SessionExerciseAPIView(_Base):
    queryset = m.SessionExercise.objects.select_related("session", "assignment")
    serializer_class = s.SessionExerciseSerializer


@registerView("remoteaccesses")
class RemoteAccessAPIView(_Base):
    """The audit trail of remote accesses: read, and end an active one."""

    queryset = m.RemoteAccessSession.objects.select_related("session", "seat__workstation", "teacher__person")
    serializer_class = s.RemoteAccessSerializer
    http_method_names = ["get", "post", "head", "options"]

    def list(self, request, *args, **kwargs):
        remote_access_service.expire_due(self.filter_queryset(self.get_queryset()))
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        raise ResaasAPIException("Open remote access from a running session.", code="method_not_allowed",
                                 status_code=405)

    @resaas_action(detail=True, methods=["post"], label="End", icon="stop_screen_share",
                   permission="end_remoteaccesssession")
    def end(self, request, pk=None):
        access = remote_access_service.end(access=self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(access).data)
