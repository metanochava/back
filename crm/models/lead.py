from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class Lead(BaseModel):
    """A potential customer not yet qualified. Converting it creates an
    Opportunity (crm.services.convert_lead)."""

    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_QUALIFIED = "qualified"
    STATUS_DISQUALIFIED = "disqualified"
    STATUS_CONVERTED = "converted"

    STATUS_CHOICES = (
        (STATUS_NEW, "New"),
        (STATUS_CONTACTED, "Contacted"),
        (STATUS_QUALIFIED, "Qualified"),
        (STATUS_DISQUALIFIED, "Disqualified"),
        (STATUS_CONVERTED, "Converted"),
    )

    SOURCE_CHOICES = (
        ("website", "Website"),
        ("referral", "Referral"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("event", "Event"),
        ("social", "Social media"),
        ("other", "Other"),
    )

    name = models.CharField(max_length=200, help_text="Contact person")
    company_name = models.CharField(max_length=200, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="other")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    owner = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="crm_leads"
    )
    disqualify_reason = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "display_name"
        search_fields = ["name", "company_name", "email", "phone"]
        crud = True
        routes = {"list": "list_lead"}

    @property
    def display_name(self):
        return f"{self.name} ({self.company_name})" if self.company_name else self.name

    def __str__(self):
        return self.display_name
