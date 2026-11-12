"""How clinical acts reach the commercial and stock modules - mappings and
records only; the clinical models stay as they are.

- ClinicalBillingRule: a clinical service -> the catalogued item(s) charged
  for it (a consultation of a specialty, or any consultation; an exam; a
  clinical medicine -> its commercial presentations).
- ExamMaterialRule: the goods an exam uses up when it is performed.
- ClinicalCharge / MaterialConsumption: what was done for one act, once
  (idempotency and traceability: the sale or the stock movements it made).

Catalogued items are loose ids (catalog), sales and movements loose ids
(sales / inventory): saude never imports their models.
"""
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel
from saude.models.clinical_document_state import active_state_field


class ClinicalBillingRule(BaseModel):
    KIND_CONSULTATION = "consultation"
    KIND_EXAM = "exam"
    KIND_MEDICATION = "medication"
    KIND_CHOICES = (
        (KIND_CONSULTATION, "Consultation"),
        (KIND_EXAM, "Exam"),
        (KIND_MEDICATION, "Medication"),
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    # consultation: of this specialty; empty = any consultation without a rule of its own
    specialty = models.ForeignKey("hr.Specialty", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="billing_rules")
    exame = models.ForeignKey("saude.ExameMedico", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="billing_rules", verbose_name="Exam")
    # a clinical medicine and one of its commercial presentations (several rules = several)
    medicamento = models.ForeignKey("saude.Medicamento", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="billing_rules", verbose_name="Medicine")
    product_id = models.UUIDField(verbose_name="Catalogued item")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Clinical billing rule"
        verbose_name_plural = "Clinical billing rules"
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "kind", "specialty", "exame", "medicamento", "product_id"],
                condition=Q(deleted_at__isnull=True), name="saude_billing_rule_unique_live",
            ),
        ]

    class RESAAS:
        label_field = "kind"
        search_fields = ["kind", "specialty__title", "exame__nome", "medicamento__descricao"]
        crud = True


class ExamMaterialRule(BaseModel):
    exame = models.ForeignKey("saude.ExameMedico", on_delete=models.CASCADE, related_name="material_rules",
                              verbose_name="Exam")
    product_id = models.UUIDField(verbose_name="Catalogued item")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exam material rule"
        verbose_name_plural = "Exam material rules"
        constraints = [
            models.UniqueConstraint(fields=["entity", "exame", "product_id"],
                                    condition=Q(deleted_at__isnull=True), name="saude_exam_material_unique_live"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="saude_exam_material_quantity_positive"),
        ]

    class RESAAS:
        label_field = "exame__nome"
        search_fields = ["exame__nome"]
        crud = True


class ClinicalCharge(BaseModel):
    """The sale (draft, in sales) made for one clinical act - one per act."""

    # a patient's record: Active from creation (saude/models/clinical_document_state.py)
    state = active_state_field()
    source_type = models.CharField(max_length=60, editable=False)
    source_id = models.UUIDField(editable=False)
    paciente = models.ForeignKey("saude.Paciente", on_delete=models.PROTECT, related_name="charges", editable=False)
    sale_id = models.UUIDField(editable=False)

    class Meta:
        verbose_name = "Clinical charge"
        verbose_name_plural = "Clinical charges"
        constraints = [
            models.UniqueConstraint(fields=["source_type", "source_id"], name="saude_clinical_charge_one_per_act"),
        ]

    class RESAAS:
        label_field = "source_type"
        search_fields = ["paciente__person__full_name"]
        crud = False


class MaterialConsumption(BaseModel):
    """The goods consumed for one performed act - one per act; `failed` keeps
    why it could not be done (no stock): the clinical act is never blocked."""

    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = ((STATUS_DONE, "Done"), (STATUS_FAILED, "Failed"))

    source_type = models.CharField(max_length=60, editable=False)
    source_id = models.UUIDField(editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, editable=False)
    movement_ids = models.JSONField(default=list, editable=False)
    reason = models.TextField(blank=True, default="", editable=False)

    class Meta:
        verbose_name = "Material consumption"
        verbose_name_plural = "Material consumptions"
        constraints = [
            models.UniqueConstraint(fields=["source_type", "source_id"], name="saude_material_consumption_one_per_act"),
        ]

    class RESAAS:
        label_field = "source_type"
        search_fields = ["source_type"]
        crud = False
