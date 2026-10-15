from decimal import Decimal
from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel


class JournalEntry(BaseModel):
    """
    A double-entry journal entry. Drafts can be edited; posting (validated:
    balanced, open period, postable accounts) numbers it and makes it
    immutable. A posted entry is corrected only by a reversal entry.

    source_event/source_id identify an entry created automatically from a
    business event (PostingRule) - unique per Entity, so the same event never
    posts twice.
    """

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_REVERSED = "reversed"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_POSTED, "Posted"),
        (STATUS_REVERSED, "Reversed"),
    )

    journal = models.ForeignKey("accounting.Journal", on_delete=models.PROTECT, related_name="entries")
    number = models.CharField(max_length=40, null=True, blank=True, editable=False)
    date = models.DateField()
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "django_resaas.User", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversed_by",
        verbose_name="Reversal of",
    )

    source_event = models.CharField(max_length=100, null=True, blank=True, editable=False)
    source_id = models.CharField(max_length=64, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Journal entry"
        verbose_name_plural = "Journal entries"
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "number"], condition=Q(number__isnull=False), name="unique_journal_entry_number_per_entity"
            ),
            models.UniqueConstraint(
                fields=["entity", "source_event", "source_id"],
                condition=Q(source_id__isnull=False),
                name="unique_journal_entry_source_per_entity",
            ),
        ]

    class RESAAS:

        label_field = "label"

        search_fields = ["number", "description", "reference"]

        crud = True

        routes = {
            "list": "list_journalentry",
            "view": "view_journalentry",
        }

    @property
    def label(self):
        return self.number or self.description

    @property
    def total_debit(self):
        return sum((line.debit for line in self.lines.all()), Decimal("0"))

    @property
    def total_credit(self):
        return sum((line.credit for line in self.lines.all()), Decimal("0"))

    def __str__(self):
        return self.label
