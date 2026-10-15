from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel
from crm.models.lead import Lead
from crm.models.opportunity import Opportunity


class Activity(BaseModel):
    """A call, e-mail, meeting, task or note about a lead or an opportunity."""

    TYPE_CHOICES = (
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("task", "Task"),
        ("note", "Note"),
    )

    activity_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="task")
    subject = models.CharField(max_length=200)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name="activities")
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.CASCADE, null=True, blank=True, related_name="activities"
    )
    due_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="crm_activities"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Activity"
        verbose_name_plural = "Activities"
        ordering = ["completed_at", "due_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(lead__isnull=False) | Q(opportunity__isnull=False), name="crm_activity_has_subject"
            ),
        ]

    class RESAAS:
        label_field = "subject"
        search_fields = ["subject", "notes"]
        crud = True
        routes = {"list": "list_activity"}

    @property
    def done(self):
        return self.completed_at is not None

    def __str__(self):
        return self.subject
