"""Structured definition of an exam (ExameMedico): its parameters and their
reference ranges. Configuration only - no clinical values are seeded here
or anywhere in code; reference ranges come from validated configuration."""
from django.core.exceptions import ValidationError
from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class ExamParameter(BaseModel):

    DECIMAL = "decimal"
    INTEGER = "integer"
    TEXT = "text"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    DATE = "date"

    DATA_TYPES = [
        (DECIMAL, "Decimal"),
        (INTEGER, "Integer"),
        (TEXT, "Text"),
        (BOOLEAN, "Yes / No"),
        # positive/negative, blood group, ... are choices
        (CHOICE, "Choice"),
        (DATE, "Date"),
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

    # offered as a time series (doctor's evolution, patient's trends). Only
    # numeric parameters can be charted: see is_graphable.
    graphable = models.BooleanField(default=True)

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

    @property
    def is_graphable(self):
        return self.graphable and self.is_numeric

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
