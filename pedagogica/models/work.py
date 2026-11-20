from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel
from django_resaas.saas.core.utils import upload_path


class Material(BaseModel):
    """A teaching material of a subject (for a class, or every class): a file
    or a link. Published, the class's students see it."""

    class_group = models.ForeignKey("academica.ClassGroup", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="materials")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="materials")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=upload_path("pedagogica/materials"), max_length=500, null=True, blank=True)
    link = models.URLField(max_length=500, blank=True, default="")
    published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materials"
        ordering = ["subject", "title"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "description", "subject__name"]
        crud = True


class Assignment(BaseModel):
    """Homework or an exercise for a class: instructions, a due date and a
    maximum score. Grading a submission can record the grade in an academica
    assessment (assignment_service)."""

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = ((STATUS_DRAFT, "Draft"), (STATUS_PUBLISHED, "Published"), (STATUS_CLOSED, "Closed"))

    class_group = models.ForeignKey("academica.ClassGroup", on_delete=models.CASCADE, related_name="assignments")
    subject = models.ForeignKey("academica.Subject", on_delete=models.PROTECT, related_name="assignments")
    teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments")
    lesson = models.ForeignKey("pedagogica.Lesson", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="assignments")
    assessment = models.ForeignKey("academica.Assessment", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="assignments", help_text="Grades go to this assessment")
    title = models.CharField(max_length=160)
    instructions = models.TextField(blank=True, default="")
    due_at = models.DateTimeField()
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=20)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT, editable=False)

    class Meta:
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"
        ordering = ["-due_at"]
        constraints = [models.CheckConstraint(condition=Q(max_score__gt=0), name="pedagogica_assignment_max_positive")]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "instructions", "subject__name", "class_group__name"]
        crud = True


class Submission(BaseModel):
    """A student's answer to an assignment (text and / or a file), once per
    enrolment; late when after the due date; graded with a score and feedback."""

    STATUS_SUBMITTED = "submitted"
    STATUS_LATE = "late"
    STATUS_GRADED = "graded"
    STATUS_CHOICES = ((STATUS_SUBMITTED, "Submitted"), (STATUS_LATE, "Late"), (STATUS_GRADED, "Graded"))

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    enrolment = models.ForeignKey("academica.Enrolment", on_delete=models.CASCADE, related_name="submissions")
    text = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=upload_path("pedagogica/submissions"), max_length=500, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SUBMITTED, editable=False)
    submitted_at = models.DateTimeField(editable=False)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, editable=False)
    feedback = models.TextField(blank=True, default="", editable=False)
    graded_by = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                  editable=False)
    graded_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["assignment", "enrolment"], condition=Q(deleted_at__isnull=True),
                                    name="pedagogica_one_submission_per_student"),
        ]

    class RESAAS:
        label_field = "enrolment__student__person__full_name"
        search_fields = ["enrolment__student__person__full_name", "assignment__title"]
        crud = True
