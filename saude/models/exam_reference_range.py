from django.core.exceptions import ValidationError
from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from saude.models.exam_parameter import ExamParameter


class ExamReferenceRange(BaseModel):
    """A reference interval of a numeric parameter, optionally restricted to
    a sex and/or an age band (in days, so newborns fit). The most specific
    matching range applies. critical_* are optional and only configured by
    the laboratory - never defaulted."""

    SEX_CHOICES = [("M", "Male"), ("F", "Female")]

    parameter = models.ForeignKey(
        ExamParameter,
        on_delete=models.CASCADE,
        related_name="reference_ranges",
    )

    sex = models.CharField(max_length=1, choices=SEX_CHOICES, null=True, blank=True)

    age_min_days = models.PositiveIntegerField(null=True, blank=True)
    age_max_days = models.PositiveIntegerField(null=True, blank=True)

    low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    critical_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    critical_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    # free description of the range (method, population) kept with the snapshot
    label = models.CharField(max_length=150, null=True, blank=True)

    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exam Reference Range"
        verbose_name_plural = "Exam Reference Ranges"
        ordering = ["parameter", "sex", "age_min_days"]

    class RESAAS:
        label_field = "label"
        search_fields = ["parameter__name", "parameter__code", "label"]
        crud = True

    def clean(self):
        errors = {}

        if self.parameter_id and not self.parameter.is_numeric:
            errors["parameter"] = "Reference ranges only apply to numeric parameters."
        if self.low is None and self.high is None:
            errors["low"] = "Define at least a low or a high limit."
        if self.low is not None and self.high is not None and self.low > self.high:
            errors["high"] = "The high limit must not be lower than the low limit."
        if (self.age_min_days is not None and self.age_max_days is not None
                and self.age_min_days > self.age_max_days):
            errors["age_max_days"] = "The maximum age must not be lower than the minimum age."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.label or f"{self.parameter.name} {self.low}-{self.high}"
