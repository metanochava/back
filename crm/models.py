from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class Stage(BaseModel):
    """A stage of the Entity's sales pipeline. Moving an opportunity to a
    stage marked is_won / is_lost closes it (crm.services.move_opportunity)."""

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    probability = models.PositiveSmallIntegerField(default=0, help_text="Chance of winning, 0-100 %")
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Stage"
        verbose_name_plural = "Stages"
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "name"], name="unique_crm_stage_name_per_entity"),
            models.CheckConstraint(condition=Q(probability__lte=100), name="crm_stage_probability_max_100"),
            models.CheckConstraint(condition=~Q(is_won=True, is_lost=True), name="crm_stage_not_won_and_lost"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name"]
        crud = True
        routes = {"list": "list_stage"}

    def __str__(self):
        return self.name


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


class Opportunity(BaseModel):
    """A deal in the pipeline. status follows its stage: open, won or lost."""

    STATUS_OPEN = "open"
    STATUS_WON = "won"
    STATUS_LOST = "lost"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_WON, "Won"),
        (STATUS_LOST, "Lost"),
    )

    title = models.CharField(max_length=200)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="opportunities")

    # loose reference to sales.Customer (crm does not require sales)
    customer_id = models.UUIDField("Customer", null=True, blank=True)

    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="opportunities")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expected_close_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="crm_opportunities"
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    lost_reason = models.TextField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Opportunity"
        verbose_name_plural = "Opportunities"
        ordering = ["-created_at"]

    class RESAAS:
        label_field = "title"
        search_fields = ["title", "lead__name", "lead__company_name"]
        crud = True
        routes = {"list": "list_opportunity", "view": "view_opportunity"}

    def __str__(self):
        return self.title


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
