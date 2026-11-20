from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class TimetableSlot(BaseModel):
    """One lesson of a class's week: a subject, at a weekday and time, with a
    teacher and a room. A class, a teacher or a room is never in two slots
    at the same time in a year (academica.services.timetable_service). The
    room belongs to laboratorio (rooms and laboratories): kept here by id and
    name, so academica imports nothing of it."""

    WEEKDAYS = ((1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"),
                (6, "Saturday"), (7, "Sunday"))

    academic_year = models.ForeignKey("academica.AcademicYear", on_delete=models.PROTECT, related_name="timetable")
    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="timetable")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="timetable")
    teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="timetable_slots")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    room_id = models.UUIDField(null=True, blank=True, help_text="A room of laboratorio")
    room_name = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        verbose_name = "Timetable slot"
        verbose_name_plural = "Timetable slots"
        ordering = ["weekday", "starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="academica_slot_ends_after_start"),
            models.CheckConstraint(condition=Q(weekday__gte=1, weekday__lte=7), name="academica_slot_weekday"),
        ]

    class RESAAS:
        label_field = "subject__name"
        search_fields = ["subject__name", "class_group__name", "teacher__person__full_name", "room_name"]
        crud = True


class PriorSchooling(BaseModel):
    """A student's schooling before this institution (a transfer in): kept as
    it was declared, so the student's history is complete."""

    student = models.ForeignKey("academica.Student", on_delete=models.CASCADE, related_name="prior_schooling")
    institution = models.CharField(max_length=160)
    academic_year = models.CharField(max_length=40, help_text="As the other institution names it, e.g. 2025")
    grade_level = models.CharField(max_length=80, blank=True, default="")
    result = models.CharField(max_length=80, blank=True, default="", help_text="e.g. Passed, 14 average")
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Prior schooling"
        verbose_name_plural = "Prior schooling"
        ordering = ["student", "academic_year"]

    class RESAAS:
        label_field = "institution"
        search_fields = ["institution", "student__person__full_name"]
        crud = True
