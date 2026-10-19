from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PatientLookup(BaseModel):
    """
    Audit of every patient lookup by code at a pharmacy: who (created_by),
    where (entity/branch), the code typed, and what it gave. Append only - the
    lookup service writes it, nothing edits it. The code LOCATES a patient; it
    never authorises: what was shown is in `outcome`.
    """

    OUTCOME_OWN = "own"                 # a patient of this Entity
    OUTCOME_CONSENT = "consent"         # another Entity's, shown under an active ConsentGrant
    OUTCOME_DENIED = "denied"           # found elsewhere, no consent: nothing shown
    OUTCOME_NOT_FOUND = "not_found"
    OUTCOME_CHOICES = (
        (OUTCOME_OWN, "Patient of this organisation"),
        (OUTCOME_CONSENT, "Shown with the patient's consent"),
        (OUTCOME_DENIED, "No consent: nothing shown"),
        (OUTCOME_NOT_FOUND, "Not found"),
    )

    code = models.CharField(verbose_name="Code", max_length=100)
    outcome = models.CharField(verbose_name="Outcome", max_length=10, choices=OUTCOME_CHOICES)
    # the Person whose records were shown (never set when nothing was shown)
    person = models.ForeignKey("django_resaas.Person", verbose_name="Person", on_delete=models.PROTECT,
                               null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "Patient lookup"
        verbose_name_plural = "Patient lookups"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "code"
        search_fields = ["code"]
        crud = False
        routes = {"list": "list_patientlookup", "view": "view_patientlookup"}

    def __str__(self):
        return f"{self.code} ({self.outcome})"
