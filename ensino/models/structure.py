"""The academic structure of an Entity (school, kindergarten, university):
grading scales, levels, programmes, grade levels, subjects, curricula,
academic years and periods. Configured once by the Entity; everything else
(classes, enrolments, grades) hangs from it."""
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class GradingScale(BaseModel):
    KIND_NUMERIC = "numeric"
    KIND_QUALITATIVE = "qualitative"
    KIND_CHOICES = ((KIND_NUMERIC, "Numeric"), (KIND_QUALITATIVE, "Qualitative"))

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default=KIND_NUMERIC)
    min_value = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_value = models.DecimalField(max_digits=6, decimal_places=2, default=20)
    pass_value = models.DecimalField(max_digits=6, decimal_places=2, default=10,
                                     help_text="Lowest numeric grade that passes")
    # qualitative: [{"value": "S", "label": "Satisfies", "passes": true}, ...]
    qualitative_values = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Grading scale"
        verbose_name_plural = "Grading scales"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(max_value__gt=models.F("min_value")), name="ensino_scale_max_above_min"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True

    def __str__(self):
        return self.name


class EducationLevel(BaseModel):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=20)
    order = models.PositiveSmallIntegerField(default=0)
    grading_scale = models.ForeignKey(GradingScale, null=True, blank=True, on_delete=models.PROTECT,
                                      related_name="levels")

    class Meta:
        verbose_name = "Education level"
        verbose_name_plural = "Education levels"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_level_code_unique"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name


class Programme(BaseModel):
    level = models.ForeignKey(EducationLevel, on_delete=models.PROTECT, related_name="programmes")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    duration_years = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Programme"
        verbose_name_plural = "Programmes"
        ordering = ["level__order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_programme_code_unique"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code", "level__name"]
        crud = True

    def __str__(self):
        return self.name


class GradeLevel(BaseModel):
    """A class / curricular year of a programme ("5th grade", "1st year")."""

    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="grade_levels")
    name = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "Grade level"
        verbose_name_plural = "Grade levels"
        ordering = ["programme__name", "order"]
        constraints = [
            models.UniqueConstraint(fields=["programme", "order"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_grade_level_order_unique"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "programme__name"]
        crud = True

    def __str__(self):
        return f"{self.programme} - {self.name}"


class Subject(BaseModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    credits = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_subject_code_unique"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code"]
        crud = True

    def __str__(self):
        return self.name


class AcademicYear(BaseModel):
    STATUS_PLANNED = "planned"
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = ((STATUS_PLANNED, "Planned"), (STATUS_OPEN, "Open"), (STATUS_CLOSED, "Closed"))

    name = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PLANNED)

    class Meta:
        verbose_name = "Academic year"
        verbose_name_plural = "Academic years"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="ensino_year_dates"),
            # one open year per branch at a time
            models.UniqueConstraint(fields=["branch"], condition=Q(status="open", deleted_at__isnull=True),
                                    name="ensino_one_open_year_per_branch"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True

    def __str__(self):
        return self.name


class AcademicPeriod(BaseModel):
    """A term / semester of an academic year (or the whole year)."""

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="periods")
    name = models.CharField(max_length=40)
    order = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name = "Academic period"
        verbose_name_plural = "Academic periods"
        ordering = ["academic_year__start_date", "order"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gt=models.F("start_date")), name="ensino_period_dates"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "academic_year__name"]
        crud = True

    def __str__(self):
        return f"{self.academic_year} - {self.name}"


class CurriculumItem(BaseModel):
    """What a grade level studies: a subject, optionally in one period."""

    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name="curriculum")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="curriculum_items")
    period_order = models.PositiveSmallIntegerField(null=True, blank=True,
                                                    help_text="Empty: the whole year; else the period's order")
    mandatory = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Curriculum item"
        verbose_name_plural = "Curriculum items"
        ordering = ["grade_level", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["grade_level", "subject", "period_order"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_curriculum_unique"),
        ]

    class RESAAS:
        label_field = "subject__name"
        search_fields = ["subject__name", "grade_level__name"]
        crud = True
