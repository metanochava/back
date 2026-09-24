from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class ResultParameterValue(BaseModel):
    """One structured value of a result (ResultadoExameMedico) for one
    parameter. It keeps a SNAPSHOT of the definition used when it was
    recorded (code, name, unit, reference, flag), so the historical record
    never changes when the exam configuration changes later.

    Values: numeric parameters in value_numeric (queryable: history,
    evolution charts), text and choice in value_text, yes/no in
    value_boolean.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"

    FLAG_CHOICES = [
        (LOW, "Low"),
        (NORMAL, "Normal"),
        (HIGH, "High"),
        (CRITICAL_LOW, "Critical low"),
        (CRITICAL_HIGH, "Critical high"),
    ]

    result = models.ForeignKey(
        "saude.ResultadoExameMedico",
        on_delete=models.CASCADE,
        related_name="parameter_values",
    )

    # the definition it answered; SET_NULL keeps the value if the parameter
    # is ever deleted (the snapshot below still describes it)
    parameter = models.ForeignKey(
        "saude.ExamParameter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="values",
    )

    # ---- snapshot of the definition at recording time ----
    parameter_code = models.CharField(max_length=50, db_index=True)
    parameter_name = models.CharField(max_length=150)
    data_type = models.CharField(max_length=20)
    unit = models.CharField(max_length=50, null=True, blank=True)
    reference_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    reference_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    reference_label = models.CharField(max_length=150, null=True, blank=True)

    # ---- value ----
    value_numeric = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    value_text = models.TextField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)

    # interpretation against the snapshot reference (never the value itself)
    flag = models.CharField(max_length=20, choices=FLAG_CHOICES, null=True, blank=True)

    recorded_by = models.ForeignKey(
        "django_resaas.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    recorded_at = models.DateTimeField()

    class Meta:
        verbose_name = "Result Parameter Value"
        verbose_name_plural = "Result Parameter Values"
        ordering = ["result", "parameter__order", "parameter_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["result", "parameter_code"],
                name="uniq_result_parameter_code",
            ),
        ]

    class RESAAS:
        label_field = "parameter_name"
        search_fields = ["parameter_name", "parameter_code"]
        crud = False

    @property
    def display_value(self):
        if self.value_numeric is not None:
            return format(self.value_numeric.normalize(), "f")
        if self.value_boolean is not None:
            return "Yes" if self.value_boolean else "No"
        return self.value_text

    def __str__(self):
        return f"{self.parameter_name}: {self.display_value}"
