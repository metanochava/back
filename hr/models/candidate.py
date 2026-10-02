from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class CandidateSource(models.TextChoices):
    WEBSITE = "website", "Website"
    REFERRAL = "referral", "Referral"
    AGENCY = "agency", "Agency"
    SOCIAL_MEDIA = "social_media", "Social Media"
    OTHER = "other", "Other"


def resume_path(instance, file_name):
    return f"hr/candidates/{instance.id}/{file_name}"


class Candidate(BaseModel):
    """A candidate is NOT a Person and NOT an Employee (pedido secção 30) -
    it only carries the identity data needed to run a recruitment process.
    A Person is looked up/created (see services/recruitment_service.py
    hire()) only once an Application actually gets hired.

    Reuses BaseModel (entity+branch required) like every other hr model
    instead of a looser tenant story: a candidate belongs to the Entity
    they first applied to, which gives the tenant-isolation guarantee
    (Entity A cannot see/hire Entity B's candidates) for free via the
    same get_queryset() filtering every other model already relies on.
    A candidate applying to more than one Entity is out of scope for this
    phase - each Entity would need its own Candidate row.

    resume is a plain FileField, not the generic Document model
    (saas/models/document.py): Document models an identity document
    with a required, unique-per-type `numero` (ID card, certificate) -
    forcing every CV upload to also carry a synthetic document number
    would be a worse fit than Django's own FileField, which Document
    itself is built on anyway.
    """

    full_name = models.CharField(max_length=200)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)

    resume = models.FileField(upload_to=resume_path, null=True, blank=True)

    source = models.CharField(
        max_length=20,
        choices=CandidateSource.choices,
        default=CandidateSource.OTHER,
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    class RESAAS:
        label_field = "full_name"
        search_fields = ["full_name", "email", "phone"]
        crud = True

    def __str__(self):
        return self.full_name
