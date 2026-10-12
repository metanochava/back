from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class PostingRule(BaseModel):
    """
    Turns a business event into an automatic journal entry, configured per
    Entity without code: when `event` is emitted with an amount, post
    debit_account / credit_account for that amount in `journal`.

    The emitting module never knows accounting exists; accounting only reads
    the event payload (accounting/listeners.py).
    """

    EVENT_PURCHASE_RECEIPT = "purchases.receipt.posted"
    EVENT_SALE_CONFIRMED = "sales.sale.confirmed"
    EVENT_SALE_PAYMENT = "sales.payment.received"

    EVENT_CHOICES = (
        (EVENT_PURCHASE_RECEIPT, "Goods received from a purchase order"),
        (EVENT_SALE_CONFIRMED, "Sale confirmed"),
        (EVENT_SALE_PAYMENT, "Sale payment received"),
    )

    event = models.CharField(max_length=100, choices=EVENT_CHOICES)
    journal = models.ForeignKey("accounting.Journal", on_delete=models.PROTECT, related_name="posting_rules")
    debit_account = models.ForeignKey(
        "accounting.Account", on_delete=models.PROTECT, related_name="debit_rules", verbose_name="Debit account"
    )
    credit_account = models.ForeignKey(
        "accounting.Account", on_delete=models.PROTECT, related_name="credit_rules", verbose_name="Credit account"
    )
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Posting rule"
        verbose_name_plural = "Posting rules"
        ordering = ["event"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "event"], name="unique_posting_rule_event_per_entity"),
        ]

    class RESAAS:

        label_field = "event"

        search_fields = ["event"]

        crud = True

        routes = {
            "list": "list_postingrule",
        }

    def __str__(self):
        return self.event
