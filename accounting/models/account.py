from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class Account(BaseModel):
    """An account of the Entity's chart of accounts. Accounts form a tree
    (parent); only accounts with allow_posting receive journal lines - the
    others group their children in reports."""

    TYPE_ASSET = "asset"
    TYPE_LIABILITY = "liability"
    TYPE_EQUITY = "equity"
    TYPE_INCOME = "income"
    TYPE_EXPENSE = "expense"

    TYPE_CHOICES = (
        (TYPE_ASSET, "Asset"),
        (TYPE_LIABILITY, "Liability"),
        (TYPE_EQUITY, "Equity"),
        (TYPE_INCOME, "Income"),
        (TYPE_EXPENSE, "Expense"),
    )

    # the side that increases the account (assets and expenses: debit)
    DEBIT_NORMAL = (TYPE_ASSET, TYPE_EXPENSE)

    code = models.CharField(max_length=30)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", verbose_name="Parent account"
    )

    allow_posting = models.BooleanField(default=True, help_text="Journal lines can be posted to this account")
    active = models.BooleanField(default=True)

    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Account"
        verbose_name_plural = "Accounts"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "code"], name="unique_account_code_per_entity"),
        ]

    class RESAAS:

        label_field = "display_name"

        search_fields = ["code", "name"]

        crud = True

        routes = {
            "list": "list_account",
        }

    @property
    def display_name(self):
        return f"{self.code} {self.name}"

    @property
    def debit_normal(self):
        return self.account_type in self.DEBIT_NORMAL

    def __str__(self):
        return self.display_name
