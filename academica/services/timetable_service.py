"""The classes' weekly timetable (TimetableSlot).

A class, a teacher or a room is never in two slots that overlap on the same
weekday of the same academic year. A room belongs to laboratorio (kept by
id), a teacher to hr.
"""
from django.db.models import Q

from academica.models import Enrolment, TimetableSlot


def clashes(*, academic_year_id, weekday, starts_at, ends_at, class_group_id, teacher_id=None, room_id=None,
            exclude_id=None):
    """{"class_group" | "teacher" | "room": the overlapping slot} for a slot
    that would be saved with these values (empty when it fits)."""
    overlapping = TimetableSlot.objects.filter(
        academic_year_id=academic_year_id, weekday=weekday, starts_at__lt=ends_at, ends_at__gt=starts_at,
    )
    if exclude_id:
        overlapping = overlapping.exclude(id=exclude_id)
    found = {}
    checks = {"class_group": Q(class_group_id=class_group_id)}
    if teacher_id:
        checks["teacher"] = Q(teacher_id=teacher_id)
    if room_id:
        checks["room"] = Q(room_id=room_id)
    for key, condition in checks.items():
        slot = overlapping.filter(condition).select_related("subject", "class_group").first()
        if slot:
            found[key] = slot
    return found


def _row(slot):
    return {
        "id": str(slot.id), "weekday": slot.weekday, "starts_at": slot.starts_at.strftime("%H:%M"),
        "ends_at": slot.ends_at.strftime("%H:%M"),
        "subject": {"id": str(slot.subject_id), "name": slot.subject.name},
        "class_group": {"id": str(slot.class_group_id), "name": slot.class_group.name},
        "teacher": ({"id": str(slot.teacher_id), "name": slot.teacher.person.full_name}
                    if slot.teacher_id else None),
        "room": {"id": str(slot.room_id) if slot.room_id else None, "name": slot.room_name} if slot.room_name or slot.room_id else None,
    }


def week(queryset, *, class_group_id=None, teacher_id=None, room_id=None, academic_year_id=None):
    """The slots of a class, a teacher or a room, by weekday and time."""
    slots = queryset.select_related("subject", "class_group", "teacher__person")
    if class_group_id:
        slots = slots.filter(class_group_id=class_group_id)
    if teacher_id:
        slots = slots.filter(teacher_id=teacher_id)
    if room_id:
        slots = slots.filter(room_id=room_id)
    if academic_year_id:
        slots = slots.filter(academic_year_id=academic_year_id)
    return [_row(slot) for slot in slots.order_by("weekday", "starts_at")]


def for_enrolment(enrolment):
    """The timetable of an enrolment's class in its year (the portal)."""
    if not enrolment.class_group_id or enrolment.status not in Enrolment.HOLDING:
        return []
    return week(TimetableSlot.objects.filter(entity_id=enrolment.entity_id), class_group_id=enrolment.class_group_id,
                academic_year_id=enrolment.academic_year_id)
