"""Structured definition of an exam (ExameMedico): its parameters and their
reference ranges. Configuration only - no clinical values are seeded here
or anywhere in code; reference ranges come from validated configuration.
"""
from django.core.exceptions import ValidationError
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class ExamParameter(BaseModel):

    DECIMAL = "decimal"
    INTEGER = "integer"
    TEXT = "text"
    BOOLEAN = "boolean"
    CHOICE = "choice"

    DATA_TYPES = [
        (DECIMAL, "Decimal"),
        (INTEGER, "Integer"),
        (TEXT, "Text"),
        (BOOLEAN, "Yes / No"),
        # positive/negative, blood group, ... are choices
        (CHOICE, "Choice"),
    ]

    NUMERIC_TYPES = (DECIMAL, INTEGER)

    exame = models.ForeignKey(
        "saude.ExameMedico",
        on_delete=models.CASCADE,
        related_name="parameters",
    )

    # stable technical key (history and evolution follow it even if the
    # display name changes)
    code = models.SlugField(max_length=50)

    name = models.CharField(max_length=150)

    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default=DECIMAL)

    unit = models.CharField(max_length=50, null=True, blank=True)

    order = models.PositiveIntegerField(default=0)

    required = models.BooleanField(default=True)

    active = models.BooleanField(default=True)

    decimal_places = models.PositiveSmallIntegerField(null=True, blank=True)

    # allowed values of a CHOICE parameter: ["Positive", "Negative"]
    choices = models.JSONField(default=list, blank=True)

    # shown to the patient once the result is released
    patient_visible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exam Parameter"
        verbose_name_plural = "Exam Parameters"
        ordering = ["exame", "order", "name"]
        unique_together = ("exame", "code")

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "code", "unit", "exame__nome"]
        crud = True

    @property
    def is_numeric(self):
        return self.data_type in self.NUMERIC_TYPES

    def clean(self):
        errors = {}

        if self.data_type == self.CHOICE:
            if not isinstance(self.choices, list) or not [c for c in self.choices if str(c).strip()]:
                errors["choices"] = "A choice parameter needs at least one choice."
        elif self.choices:
            errors["choices"] = "Only a choice parameter has choices."

        if self.decimal_places is not None and self.data_type != self.DECIMAL:
            errors["decimal_places"] = "Only a decimal parameter has decimal places."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.exame.nome} - {self.name}"


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
