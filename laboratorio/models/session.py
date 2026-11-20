from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class LabSession(BaseModel):
    """A practical session of a class in a room: planned -> running -> ended
    (or cancelled). Students are seated at workstations; exercises
    (pedagogica assignments) are distributed; while it runs, its teacher may
    open audited remote access to a seated student's workstation."""

    STATUS_PLANNED = "planned"
    STATUS_RUNNING = "running"
    STATUS_ENDED = "ended"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = ((STATUS_PLANNED, "Planned"), (STATUS_RUNNING, "Running"), (STATUS_ENDED, "Ended"),
                      (STATUS_CANCELLED, "Cancelled"))

    room = models.ForeignKey("laboratorio.Room", on_delete=models.PROTECT, related_name="sessions")
    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="lab_sessions")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="lab_sessions")
    teacher = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="lab_sessions")
    environment = models.ForeignKey("laboratorio.Environment", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="sessions")
    title = models.CharField(max_length=160)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PLANNED, editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Lab session"
        verbose_name_plural = "Lab sessions"
        ordering = ["-starts_at"]
        constraints = [models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")),
                                              name="laboratorio_session_ends_after_start")]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "class_group__name", "subject__name", "room__name"]
        crud = True


class SeatAssignment(BaseModel):
    """A student (enrolment) at a workstation in a session: one workstation
    per student and one student per workstation."""

    session = models.ForeignKey(LabSession, on_delete=models.CASCADE, related_name="seats")
    enrolment = models.ForeignKey("academica.Enrolment", on_delete=models.CASCADE, related_name="lab_seats")
    workstation = models.ForeignKey("laboratorio.Workstation", on_delete=models.PROTECT, related_name="seats")
    checked_in_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Seat assignment"
        verbose_name_plural = "Seat assignments"
        ordering = ["workstation__code"]
        constraints = [
            models.UniqueConstraint(fields=["session", "workstation"], condition=Q(deleted_at__isnull=True),
                                    name="laboratorio_one_student_per_workstation"),
            models.UniqueConstraint(fields=["session", "enrolment"], condition=Q(deleted_at__isnull=True),
                                    name="laboratorio_one_workstation_per_student"),
        ]

    class RESAAS:
        label_field = "workstation__code"
        search_fields = ["enrolment__student__person__full_name", "workstation__code"]
        crud = True


class SessionExercise(BaseModel):
    """An exercise distributed in a session: a pedagogica assignment of the
    session's class."""

    session = models.ForeignKey(LabSession, on_delete=models.CASCADE, related_name="exercises")
    assignment = models.ForeignKey("pedagogica.Assignment", on_delete=models.CASCADE, related_name="lab_sessions")

    class Meta:
        verbose_name = "Session exercise"
        verbose_name_plural = "Session exercises"
        constraints = [models.UniqueConstraint(fields=["session", "assignment"], condition=Q(deleted_at__isnull=True),
                                               name="laboratorio_exercise_once_per_session")]

    class RESAAS:
        label_field = "assignment__title"
        crud = True


class RemoteAccessSession(BaseModel):
    """A teacher's remote access to a seated student's workstation, during a
    running session, with a reason and a time limit; never hidden - the
    student sees it (remote_access_service), every start and end is audited."""

    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = ((STATUS_ACTIVE, "Active"), (STATUS_ENDED, "Ended"), (STATUS_EXPIRED, "Expired"))

    session = models.ForeignKey(LabSession, on_delete=models.CASCADE, related_name="remote_accesses")
    seat = models.ForeignKey(SeatAssignment, on_delete=models.CASCADE, related_name="remote_accesses")
    teacher = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="remote_accesses")
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_ACTIVE, editable=False)
    started_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(editable=False)
    ended_at = models.DateTimeField(null=True, blank=True, editable=False)
    ended_by = models.ForeignKey("django_resaas.User", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+", editable=False)
    external_ref = models.CharField(max_length=200, blank=True, default="", editable=False)
    access_url = models.CharField(max_length=500, blank=True, default="", editable=False)

    class Meta:
        verbose_name = "Remote access"
        verbose_name_plural = "Remote accesses"
        ordering = ["-started_at"]
        constraints = [models.UniqueConstraint(fields=["seat"], condition=Q(status="active", deleted_at__isnull=True),
                                               name="laboratorio_one_active_remote_access_per_seat")]

    class RESAAS:
        label_field = "reason"
        search_fields = ["reason", "seat__workstation__code", "teacher__person__full_name"]
        crud = False
