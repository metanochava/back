from django.contrib import admin

from django_resaas.saas.core.base.admin import BaseAdmin, all_fields

from accounting.models import Account, FiscalPeriod, Journal, JournalEntry, JournalEntryLine, PostingRule


@admin.register(Account, Journal, FiscalPeriod, JournalEntry, JournalEntryLine, PostingRule)
class AccountingAdmin(BaseAdmin):
    list_display = ("id",)

    def get_list_display(self, request):
        return all_fields(self.model)
