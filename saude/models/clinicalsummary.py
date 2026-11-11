from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from saude.models.clinical_document_state import active_state_field


class ClinicalSummary(BaseModel):

    # Active from creation (the right-menu history lists only Active ones)
    state = active_state_field()
    """Clinical summary (resumo clínico): a structured, signed account of a
    patient's case - history, findings, diagnoses, investigations, treatment,
    clinical course and recommendations - issued at a consultation (for a
    referral, a second opinion, the patient or an insurer). Its text is what
    the doctor reviewed and issued: suggested from the record
    (clinical_summary_service.draft), never re-read from it later."""

    consulta = models.ForeignKey(
        "saude.Consulta",
        on_delete=models.CASCADE,
        related_name="clinical_summaries",
    )

    # who it is for / why it was issued (e.g. referral, insurer, patient's request)
    purpose = models.CharField(max_length=200, null=True, blank=True)

    # rich text (s-editor), in the order of the document
    history = models.TextField(null=True, blank=True)
    findings = models.TextField(null=True, blank=True)
    diagnoses = models.TextField(null=True, blank=True)
    investigations = models.TextField(null=True, blank=True)
    treatment = models.TextField(null=True, blank=True)
    clinical_course = models.TextField(null=True, blank=True)
    recommendations = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Clinical summary"
        verbose_name_plural = "Clinical summaries"

    class RESAAS:
        label_field = "consulta.paciente.person.full_name"

        search_fields = [
            "consulta__paciente__person__full_name",
            "consulta__employee__person__full_name",
            "purpose",
            "diagnoses",
        ]

        crud = True

        routes = {
            "list": "list_clinicalsummary",
            "view": "view_clinicalsummary",
            "add": "add_clinicalsummary",
            "change": "change_clinicalsummary",
        }

    def __str__(self):
        paciente = getattr(self.consulta.paciente.person, "full_name", "Patient")
        return f"Clinical summary - {paciente}"
