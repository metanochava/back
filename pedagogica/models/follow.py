from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class CalendarEvent(BaseModel):
    """The pedagogical calendar: tests, homework, activities, meetings,
    holidays - of a class (or the whole school when no class)."""

    KIND_CHOICES = (("test", "Test"), ("homework", "Homework"), ("activity", "Activity"), ("meeting", "Meeting"),
                    ("holiday", "Holiday"))

    class_group = models.ForeignKey("academica.ClassGroup", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="calendar_events")
    subject = models.ForeignKey("academica.Subject", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="calendar_events")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="activity")
    title = models.CharField(max_length=160)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Calendar event"
        verbose_name_plural = "Calendar events"
        ordering = ["starts_at"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "description"]
        crud = True


class ProgressNote(BaseModel):
    """A teacher's note on a student's progress (an observation, something
    positive, a concern), optionally shared with the student and guardians."""

    KIND_CHOICES = (("observation", "Observation"), ("positive", "Positive"), ("concern", "Concern"))

    enrolment = models.ForeignKey("academica.Enrolment", on_delete=models.CASCADE, related_name="progress_notes")
    subject = models.ForeignKey("academica.Subject", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="progress_notes")
    teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="progress_notes")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="observation")
    note = models.TextField()
    shared = models.BooleanField(default=False, help_text="The student and the guardians see it")

    class Meta:
        verbose_name = "Progress note"
        verbose_name_plural = "Progress notes"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "kind"
        search_fields = ["note", "enrolment__student__person__full_name"]
        crud = True


class ClassMessage(BaseModel):
    """A teacher's message to a class (and its guardians): homework reminders,
    news of the subject."""

    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="messages")
    subject = models.ForeignKey("academica.Subject", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="class_messages")
    title = models.CharField(max_length=160)
    body = models.TextField()
    published = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Class message"
        verbose_name_plural = "Class messages"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "body"]
        crud = True
