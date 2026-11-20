"""Practical sessions: a class in a room with its teacher.

planned -> running -> ended, planned -> cancelled (never back). Ending a
session ends its open remote accesses. A room holds one planned / running
session at a time; a student sits at one workstation of the session's room,
one student per workstation; an exercise is an assignment of the session's
class.
"""
from django.db import transaction
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services import audit_service

from laboratorio.models import LabSession, RemoteAccessSession

TRANSITIONS = {
    LabSession.STATUS_PLANNED: {LabSession.STATUS_RUNNING, LabSession.STATUS_CANCELLED},
    LabSession.STATUS_RUNNING: {LabSession.STATUS_ENDED},
}


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, status_code=status_code,
                              details={field: [message]} if field else None)


def check_room_free(*, room, starts_at, ends_at, exclude_id=None):
    clash = LabSession.objects.filter(
        room=room, status__in=(LabSession.STATUS_PLANNED, LabSession.STATUS_RUNNING),
        starts_at__lt=ends_at, ends_at__gt=starts_at,
    )
    if exclude_id:
        clash = clash.exclude(id=exclude_id)
    if clash.exists():
        raise _error("The room already has a session at this time.", "room", code="room_busy", status_code=409)


def check_seat(*, session, enrolment, workstation):
    if enrolment.class_group_id != session.class_group_id:
        raise _error("The student is not of the session's class.", "enrolment")
    if workstation.room_id != session.room_id:
        raise _error("The workstation is not in the session's room.", "workstation")
    if workstation.status != "available":
        raise _error("The workstation is not available.", "workstation")


def check_exercise(*, session, assignment):
    if assignment.class_group_id != session.class_group_id:
        raise _error("The assignment is not of the session's class.", "assignment")


def _transition(session, to, user, request=None):
    with transaction.atomic():
        session = LabSession.objects.select_for_update().get(pk=session.pk)
        if to not in TRANSITIONS.get(session.status, set()):
            raise _error(f"A {session.status} session cannot become {to}.", "status", code="invalid_transition",
                         status_code=409)
        previous, session.status, session.updated_by = session.status, to, user
        fields = ["status", "updated_by", "updated_at"]
        now = timezone.now()
        if to == LabSession.STATUS_RUNNING:
            session.started_at = now
            fields.append("started_at")
        if to == LabSession.STATUS_ENDED:
            session.ended_at = now
            fields.append("ended_at")
        session.save(update_fields=fields)
        audit_service.record(action="LAB_SESSION_" + to.upper(), target=session, actor=user, request=request,
                             entity_id=session.entity_id, details={"from": previous, "to": to})
    if to == LabSession.STATUS_ENDED:
        from laboratorio.services import remote_access_service

        for access in RemoteAccessSession.objects.filter(session=session, status=RemoteAccessSession.STATUS_ACTIVE):
            remote_access_service.end(access=access, user=user, request=request, reason="session ended")
    EventDispatcher.emit(f"laboratorio.session.{to}", instance=session, actor=user,
                         context={"session_id": str(session.id), "class_group_id": str(session.class_group_id)})
    return session


def start(*, session, user, request=None):
    return _transition(session, LabSession.STATUS_RUNNING, user, request)


def end(*, session, user, request=None):
    return _transition(session, LabSession.STATUS_ENDED, user, request)


def cancel(*, session, user, request=None):
    return _transition(session, LabSession.STATUS_CANCELLED, user, request)
