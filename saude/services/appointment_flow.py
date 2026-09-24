"""Patient flow of an appointment (Agenda): state-transition timestamps and
the waiting-time metrics built on them.

Two different metrics, never mixed:
- waiting time  = check-in -> service start (how long the PATIENT waited);
- delay         = scheduled time -> service start (how late the SERVICE was).

Example: scheduled 10:00, check-in 09:50, doctor starts 10:17
-> waiting 27 min, delay 17 min.

Timestamps are stamped by the server whenever `estado` moves into the state
(PATCH from the patient screen or any other path), once: a repeated
transition never overwrites the first time.
"""
from datetime import datetime

from django.conf import settings
from django.utils import timezone

WAITING = "em_espera"
IN_PROGRESS = "em_atendimento"
COMPLETED = "concluida"
CLOSED_WITHOUT_SERVICE = {"cancelada", "faltou"}

# state -> the timestamp field the transition into it sets
TRANSITION_TIMESTAMPS = {
    WAITING: "checked_in_at",
    IN_PROGRESS: "service_started_at",
    COMPLETED: "completed_at",
}

# Default UI bands, in minutes (Normal <= attention_after < Attention <=
# long_wait_after < Long wait). Configurable defaults, not clinical rules:
# override with settings.SAUDE_WAITING_THRESHOLDS.
DEFAULT_WAITING_THRESHOLDS = {"attention_after": 15, "long_wait_after": 30}


def waiting_thresholds():
    return {**DEFAULT_WAITING_THRESHOLDS, **getattr(settings, "SAUDE_WAITING_THRESHOLDS", {})}


def stamp_transition(agenda, previous_estado, now=None):
    """Sets the timestamp of the state `agenda.estado` just moved into.
    Returns the list of fields it set (to pass to save(update_fields=...))."""

    if agenda.estado == previous_estado:
        return []

    field = TRANSITION_TIMESTAMPS.get(agenda.estado)

    if not field or getattr(agenda, field):
        return []

    setattr(agenda, field, now or timezone.now())
    return [field]


def scheduled_at(agenda):
    moment = datetime.combine(agenda.data, agenda.hora_inicio)
    return timezone.make_aware(moment) if timezone.is_naive(moment) else moment


def _minutes(start, end):
    return max(0, int((end - start).total_seconds() // 60))


def waiting_minutes(agenda, now=None):
    """Minutes between check-in and the start of the service - or until
    `now` while the patient is still waiting. None when there was no
    check-in, or the appointment closed without being served."""

    if not agenda.checked_in_at:
        return None

    if agenda.service_started_at:
        return _minutes(agenda.checked_in_at, agenda.service_started_at)

    if agenda.estado == WAITING:
        return _minutes(agenda.checked_in_at, now or timezone.now())

    return None


def delay_minutes(agenda):
    """Minutes the service started after the scheduled time (0 when it
    started on time or early). None until the service starts."""

    if not agenda.service_started_at:
        return None

    return _minutes(scheduled_at(agenda), agenda.service_started_at)


def waiting_band(minutes):
    """'normal' | 'attention' | 'long_wait' | None, for the UI badge."""

    if minutes is None:
        return None

    thresholds = waiting_thresholds()

    if minutes > thresholds["long_wait_after"]:
        return "long_wait"

    if minutes > thresholds["attention_after"]:
        return "attention"

    return "normal"
