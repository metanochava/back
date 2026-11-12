"""Teaching, assessment, grades, attendance and tuition (second delivery).
Grades are auditable: once recorded a grade changes only through
grading_service.amend (a reason, the previous value kept in GradeRevision)."""
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class TeachingAssignment(BaseModel):
    """Who teaches a subject to a class (in one period, or the whole year)."""

    class_group = models.ForeignKey("ensino.ClassGroup", on_delete=models.CASCADE, related_name="teaching")
    subject = models.ForeignKey("ensino.Subject", on_delete=models.PROTECT, related_name="teaching")
    teacher = models.ForeignKey("hr.Employee", on_delete=models.PROTECT, related_name="teaching_assignments")
    period = models.ForeignKey("ensino.AcademicPeriod", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="teaching")

    class Meta:
        verbose_name = "Teaching assignment"
        verbose_name_plural = "Teaching assignments"
        constraints = [
            models.UniqueConstraint(fields=["class_group", "subject", "period"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_one_teacher_per_class_subject_period"),
        ]

    class RESAAS:
        label_field = "subject__name"
        search_fields = ["subject__name", "class_group__name", "teacher__person__full_name"]
        crud = True


class Assessment(BaseModel):
    KIND_CHOICES = (("test", "Test"), ("exam", "Exam"), ("assignment", "Assignment"), ("oral", "Oral"),
                    ("project", "Project"), ("other", "Other"))

    class_group = models.ForeignKey("ensino.ClassGroup", on_delete=models.CASCADE, related_name="assessments")
    subject = models.ForeignKey("ensino.Subject", on_delete=models.PROTECT, related_name="assessments")
    period = models.ForeignKey("ensino.AcademicPeriod", on_delete=models.PROTECT, related_name="assessments")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="test")
    date = models.DateField()
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    class Meta:
        verbose_name = "Assessment"
        verbose_name_plural = "Assessments"
        ordering = ["-date"]
        constraints = [models.CheckConstraint(condition=Q(weight__gt=0), name="ensino_assessment_weight_positive")]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "subject__name", "class_group__name"]
        crud = True

    def __str__(self):
        return self.name


class Grade(BaseModel):
    """A student's grade in an assessment (numeric, or a qualitative value of
    the level's scale); absent = did not take it."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="grades")
    enrolment = models.ForeignKey("ensino.Enrolment", on_delete=models.PROTECT, related_name="grades")
    value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    qualitative_value = models.CharField(max_length=20, blank=True, default="")
    absent = models.BooleanField(default=False)
    comment = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Grade"
        verbose_name_plural = "Grades"
        constraints = [
            models.UniqueConstraint(fields=["assessment", "enrolment"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_one_grade_per_assessment"),
        ]

    class RESAAS:
        label_field = "enrolment__student__person__full_name"
        search_fields = ["enrolment__student__person__full_name", "assessment__name"]
        crud = True


class GradeRevision(BaseModel):
    """A grade that changed after it was recorded: what it was, what it became and why."""

    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="revisions", editable=False)
    previous_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, editable=False)
    previous_qualitative = models.CharField(max_length=20, blank=True, default="", editable=False)
    previous_absent = models.BooleanField(default=False, editable=False)
    new_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, editable=False)
    new_qualitative = models.CharField(max_length=20, blank=True, default="", editable=False)
    new_absent = models.BooleanField(default=False, editable=False)
    reason = models.TextField(editable=False)

    class Meta:
        verbose_name = "Grade revision"
        verbose_name_plural = "Grade revisions"
        ordering = ["created_at"]

    class RESAAS:
        label_field = "reason"
        search_fields = ["grade__enrolment__student__person__full_name"]
        crud = False


class StudentAttendance(BaseModel):
    STATUS_CHOICES = (("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("excused", "Excused absence"))

    enrolment = models.ForeignKey("ensino.Enrolment", on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()
    # empty: the whole day; else one lesson of a subject
    subject = models.ForeignKey("ensino.Subject", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="attendance")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="present")
    justification = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Student attendance"
        verbose_name_plural = "Student attendance"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["enrolment", "date", "subject"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_one_attendance_per_lesson"),
        ]

    class RESAAS:
        label_field = "status"
        search_fields = ["enrolment__student__person__full_name"]
        crud = True


class TuitionRule(BaseModel):
    """What an enrolment is charged (a catalogued item): the enrolment fee when
    it becomes active, the monthly fee each month. A grade level's rule wins
    over its programme's."""

    KIND_ENROLMENT = "enrolment_fee"
    KIND_MONTHLY = "monthly_fee"
    KIND_CHOICES = ((KIND_ENROLMENT, "Enrolment fee"), (KIND_MONTHLY, "Monthly fee"))

    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    programme = models.ForeignKey("ensino.Programme", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="tuition_rules")
    grade_level = models.ForeignKey("ensino.GradeLevel", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="tuition_rules")
    product_id = models.UUIDField(verbose_name="Catalogued item")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tuition rule"
        verbose_name_plural = "Tuition rules"
        constraints = [
            models.CheckConstraint(condition=Q(programme__isnull=False) | Q(grade_level__isnull=False),
                                   name="ensino_tuition_rule_has_a_target"),
        ]

    class RESAAS:
        label_field = "kind"
        search_fields = ["kind", "programme__name", "grade_level__name"]
        crud = True


class TuitionCharge(BaseModel):
    """The sale (in sales) made for an enrolment's fee - one per enrolment
    and kind (and month for the monthly fee)."""

    enrolment = models.ForeignKey("ensino.Enrolment", on_delete=models.PROTECT, related_name="charges", editable=False)
    kind = models.CharField(max_length=16, choices=TuitionRule.KIND_CHOICES, editable=False)
    month = models.DateField(null=True, blank=True, editable=False, help_text="First day of the month charged")
    sale_id = models.UUIDField(editable=False)

    class Meta:
        verbose_name = "Tuition charge"
        verbose_name_plural = "Tuition charges"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["enrolment", "kind", "month"], name="ensino_tuition_charge_once"),
            models.UniqueConstraint(fields=["enrolment", "kind"], condition=Q(month__isnull=True),
                                    name="ensino_enrolment_fee_once"),
        ]

    class RESAAS:
        label_field = "kind"
        search_fields = ["enrolment__student__person__full_name"]
        crud = False
