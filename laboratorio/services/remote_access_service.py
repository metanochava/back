"""Remote access to a student's workstation - authorised, limited, visible,
audited.

- Only while the session is running, only by the session's own teacher (the
  signed-in user's Employee), only to a workstation where a student of the
  session sits, with a reason, for 1 to 60 minutes (default 15).
- One active access per seat. It ends by the teacher, by the session ending,
  or by expiry (checked whenever accesses are read: expire_due()).
- The student sees it (labsessions/mine/). Every start, end and expiry is an
  AuditLog row (LAB_REMOTE_ACCESS_STARTED / _ENDED / _EXPIRED); the start
  emits laboratorio.remote_access.started.
- The Lab Manager adapter opens it there when connected; when it refuses, no
  access is recorded (502).
"""
import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services import audit_service

from laboratorio.integrations.labmanager import get_adapter
from laboratorio.models import LabSession, RemoteAccessSession

DEFAULT_MINUTES = 15
MAX_MINUTES = 60


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, status_code=status_code,
                              details={field: [message]} if field else None)


def expire_due(queryset=None):
    now = timezone.now()
    due = (queryset if queryset is not None else RemoteAccessSession.objects).filter(
        status=RemoteAccessSession.STATUS_ACTIVE, expires_at__lte=now)
    for access in due:
        with transaction.atomic():
            access.status, access.ended_at = RemoteAccessSession.STATUS_EXPIRED, access.expires_at
            access.save(update_fields=["status", "ended_at", "updated_at"])
            audit_service.record(action="LAB_REMOTE_ACCESS_EXPIRED", target=access, entity_id=access.entity_id,
                                 details={"seat_id": str(access.seat_id)})
        _close_remote(access)


def _close_remote(access):
    if access.external_ref:
        try:
            get_adapter().end_remote_access(ref=access.external_ref)
        except Exception:  # noqa: BLE001 - recorded as ended here; the Lab Manager's own expiry closes it
            pass


def start(*, seat, teacher, reason, minutes=None, user, request=None):
    session = seat.session
    if session.status != LabSession.STATUS_RUNNING:
        raise _error("Remote access only during a running session.", "session", code="session_not_running",
                     status_code=409)
    if teacher is None or teacher.pk != session.teacher_id:
        raise _error("Only the session's teacher may open remote access.", code="not_session_teacher",
                     status_code=403)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _error("Give the reason for the remote access.", "reason")
    try:
        minutes = int(minutes or DEFAULT_MINUTES)
    except (TypeError, ValueError):
        raise _error("Invalid duration.", "minutes")
    if not 1 <= minutes <= MAX_MINUTES:
        raise _error(f"The duration is between 1 and {MAX_MINUTES} minutes.", "minutes")

    expire_due(RemoteAccessSession.objects.filter(seat=seat))
    now = timezone.now()
    expires_at = min(now + datetime.timedelta(minutes=minutes), max(session.ends_at, now + datetime.timedelta(minutes=1)))
    adapter = get_adapter()
    try:
        opened = adapter.start_remote_access(workstation=seat.workstation, teacher=teacher, session=session,
                                             expires_at=expires_at)
    except Exception:  # noqa: BLE001 - the Lab Manager refused: nothing recorded
        raise _error("The remote access tool could not open the remote access.", code="labmanager_failed", status_code=502)
    try:
        with transaction.atomic():
            access = RemoteAccessSession.objects.create(
                entity_id=session.entity_id, branch_id=session.branch_id, created_by=user, updated_by=user,
                session=session, seat=seat, teacher=teacher, reason=reason, started_at=now, expires_at=expires_at,
                external_ref=(opened or {}).get("ref", ""), access_url=(opened or {}).get("url", ""),
            )
            audit_service.record(action="LAB_REMOTE_ACCESS_STARTED", target=access, actor=user, request=request,
                                 entity_id=session.entity_id,
                                 details={"seat_id": str(seat.id), "workstation": seat.workstation.code,
                                          "enrolment_id": str(seat.enrolment_id), "reason": reason,
                                          "expires_at": expires_at.isoformat(), "provider": adapter.name})
    except IntegrityError:
        if opened and opened.get("ref"):
            _close_remote(type("A", (), {"external_ref": opened["ref"]})())
        raise _error("This workstation already has an active remote access.", code="already_active", status_code=409)
    EventDispatcher.emit("laboratorio.remote_access.started", instance=access, actor=user,
                         context={"access_id": str(access.id), "session_id": str(session.id),
                                  "enrolment_id": str(seat.enrolment_id)})
    return access


def end(*, access, user, request=None, reason="ended by the teacher"):
    with transaction.atomic():
        access = RemoteAccessSession.objects.select_for_update().get(pk=access.pk)
        if access.status != RemoteAccessSession.STATUS_ACTIVE:
            return access
        access.status, access.ended_at = RemoteAccessSession.STATUS_ENDED, timezone.now()
        access.ended_by = user if getattr(user, "pk", None) else None
        access.updated_by = access.ended_by
        access.save(update_fields=["status", "ended_at", "ended_by", "updated_by", "updated_at"])
        audit_service.record(action="LAB_REMOTE_ACCESS_ENDED", target=access, actor=user, request=request,
                             entity_id=access.entity_id, details={"seat_id": str(access.seat_id), "why": reason})
    _close_remote(access)
    return access
