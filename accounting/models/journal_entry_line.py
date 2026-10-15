from django.db import models
from django.db.models import Q
from django_resaas.saas.core.base.models import BaseModel


class JournalEntryLine(BaseModel):
    """One side of an entry: exactly one of debit / credit is > 0."""

    entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.CASCADE, related_name="lines", verbose_name="Journal entry"
    )
    account = models.ForeignKey("accounting.Account", on_delete=models.PROTECT, related_name="lines")
    description = models.CharField(max_length=255, null=True, blank=True)
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Journal entry line"
        verbose_name_plural = "Journal entry lines"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0)),
                name="journal_line_debit_xor_credit",
            ),
        ]

    class RESAAS:

        label_field = "label"

        search_fields = ["account__code", "account__name", "description"]

        crud = True

        routes = {
            "list": "list_journalentryline",
            "view": "view_journalentryline",
        }

    @property
    def label(self):
        return self.account.display_name if self.account_id else "-"

    def __str__(self):
        return f"{self.label} D{self.debit} C{self.credit}"
