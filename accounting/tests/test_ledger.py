"""Accounting: double-entry invariants, posting, reversal, periods, trial
balance, tenant isolation, permissions, and automatic entries from events."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from django_resaas.saas.core.events import EventDispatcher
from testutils.tenant import bootstrap_tenant

from accounting import services
from accounting.models import Account, FiscalPeriod, Journal, JournalEntry, JournalEntryLine, PostingRule

ACTIONS = (
    "post_entry_journalentry", "reverse_journalentry",
    "close_fiscalperiod", "reopen_fiscalperiod", "trial_balance_account",
)


def fields(tenant):
    return dict(entity=tenant["entity"], branch=tenant["branch"], created_by=tenant["user"], updated_by=tenant["user"])


def chart(tenant):
    cash = Account.objects.create(code="11", name="Cash", account_type=Account.TYPE_ASSET, **fields(tenant))
    revenue = Account.objects.create(code="71", name="Sales revenue", account_type=Account.TYPE_INCOME, **fields(tenant))
    group = Account.objects.create(
        code="1", name="Assets", account_type=Account.TYPE_ASSET, allow_posting=False, **fields(tenant)
    )
    journal = Journal.objects.create(code="GEN", name="General", **fields(tenant))
    return cash, revenue, group, journal


def entry(tenant, journal, lines, date=None):
    e = JournalEntry.objects.create(
        journal=journal, date=date or timezone.localdate(), description="Test", **fields(tenant)
    )
    for account, debit, credit in lines:
        JournalEntryLine.objects.create(
            entry=e, account=account, debit=Decimal(debit), credit=Decimal(credit), **fields(tenant)
        )
    return e


class LedgerApiTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("acc", modules=("accounting",), extra_permissions=ACTIONS)
        self.client = self.tenant["client"]
        self.cash, self.revenue, self.group, self.journal = chart(self.tenant)

    def _post(self, e):
        return self.client.post(f"/api/accounting/journalentries/{e.id}/post/")

    def test_balanced_entry_posts_with_a_number_and_freezes(self):
        e = entry(self.tenant, self.journal, [(self.cash, "100", "0"), (self.revenue, "0", "100")])

        response = self._post(e)
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data["status"]["value"], "posted")
        self.assertEqual(response.data["number"], f"GEN-{timezone.localdate().year}-000001")

        self.assertEqual(self.client.patch(f"/api/accounting/journalentries/{e.id}/", {"description": "x"}, format="json").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/accounting/journalentries/{e.id}/").status_code, 409)
        line = e.lines.first()
        self.assertEqual(self.client.patch(f"/api/accounting/journalentrylines/{line.id}/", {"debit": "1"}, format="json").status_code, 409)
        self.assertEqual(self._post(e).status_code, 409)

    def test_unbalanced_or_short_entries_are_refused(self):
        unbalanced = entry(self.tenant, self.journal, [(self.cash, "100", "0"), (self.revenue, "0", "90")])
        response = self._post(unbalanced)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "journal_entry_unbalanced")

        single = entry(self.tenant, self.journal, [(self.cash, "100", "0")])
        self.assertEqual(self._post(single).data["error"]["code"], "journal_entry_too_few_lines")

    def test_grouping_account_does_not_accept_postings(self):
        e = entry(self.tenant, self.journal, [(self.group, "10", "0"), (self.revenue, "0", "10")])
        self.assertEqual(self._post(e).data["error"]["code"], "account_not_postable")

    def test_line_is_debit_xor_credit(self):
        e = entry(self.tenant, self.journal, [])
        for debit, credit in (("5", "5"), ("0", "0"), ("-1", "0")):
            response = self.client.post("/api/accounting/journalentrylines/", {
                "entry": str(e.id), "account": str(self.cash.id), "debit": debit, "credit": credit,
            }, format="json")
            self.assertEqual(response.status_code, 400, (debit, credit))

    def test_reversal_swaps_lines_and_nets_to_zero(self):
        e = entry(self.tenant, self.journal, [(self.cash, "100", "0"), (self.revenue, "0", "100")])
        self._post(e)

        response = self.client.post(f"/api/accounting/journalentries/{e.id}/reverse/", {}, format="json")
        self.assertEqual(response.status_code, 202, response.data)
        reversal = JournalEntry.objects.get(id=response.data["id"])
        self.assertEqual(reversal.reversal_of_id, e.id)
        self.assertEqual(reversal.status, JournalEntry.STATUS_POSTED)
        e.refresh_from_db()
        self.assertEqual(e.status, JournalEntry.STATUS_REVERSED)

        self.assertEqual(self.client.post(f"/api/accounting/journalentries/{e.id}/reverse/").status_code, 409)
        self.assertEqual(self.client.post(f"/api/accounting/journalentries/{reversal.id}/reverse/").status_code, 409)

        balance = self.client.get("/api/accounting/accounts/trial_balance/").data
        cash = next(row for row in balance["rows"] if row["code"] == "11")
        self.assertEqual(Decimal(str(cash["balance"])), Decimal("0"))

    def test_trial_balance_balances_and_respects_dates(self):
        e1 = entry(self.tenant, self.journal, [(self.cash, "100", "0"), (self.revenue, "0", "100")], date=datetime.date(2026, 1, 10))
        e2 = entry(self.tenant, self.journal, [(self.cash, "40", "0"), (self.revenue, "0", "40")], date=datetime.date(2026, 2, 10))
        draft = entry(self.tenant, self.journal, [(self.cash, "7", "0"), (self.revenue, "0", "7")], date=datetime.date(2026, 2, 11))
        services.post_entry(entry=e1, user=self.tenant["user"])
        services.post_entry(entry=e2, user=self.tenant["user"])

        data = self.client.get("/api/accounting/accounts/trial_balance/").data
        self.assertEqual(Decimal(str(data["total_debit"])), Decimal("140"))
        self.assertEqual(data["total_debit"], data["total_credit"])
        revenue = next(row for row in data["rows"] if row["code"] == "71")
        self.assertEqual(Decimal(str(revenue["balance"])), Decimal("140"))  # income: credit-normal

        data = self.client.get("/api/accounting/accounts/trial_balance/", {"date_from": "2026-02-01"}).data
        self.assertEqual(Decimal(str(data["total_debit"])), Decimal("40"))
        self.assertTrue(JournalEntry.objects.filter(id=draft.id, status="draft").exists())

        self.assertEqual(self.client.get("/api/accounting/accounts/trial_balance/", {"date_to": "x"}).status_code, 400)

    def test_closed_period_blocks_posting_and_drafts_block_closing(self):
        period = FiscalPeriod.objects.create(
            name="2026-01", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 1, 31), **fields(self.tenant)
        )
        draft = entry(self.tenant, self.journal, [(self.cash, "10", "0"), (self.revenue, "0", "10")], date=datetime.date(2026, 1, 5))

        response = self.client.post(f"/api/accounting/fiscalperiods/{period.id}/close/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "fiscal_period_has_drafts")

        draft.delete()
        self.assertEqual(self.client.post(f"/api/accounting/fiscalperiods/{period.id}/close/").status_code, 202)

        late = entry(self.tenant, self.journal, [(self.cash, "10", "0"), (self.revenue, "0", "10")], date=datetime.date(2026, 1, 20))
        self.assertEqual(self._post(late).data["error"]["code"], "fiscal_period_closed")

        outside = entry(self.tenant, self.journal, [(self.cash, "10", "0"), (self.revenue, "0", "10")], date=datetime.date(2025, 6, 1))
        self.assertEqual(self._post(outside).data["error"]["code"], "no_fiscal_period")

        self.assertEqual(self.client.post(f"/api/accounting/fiscalperiods/{period.id}/reopen/").status_code, 202)
        self.assertEqual(self._post(late).status_code, 202)

    def test_overlapping_periods_are_refused(self):
        FiscalPeriod.objects.create(
            name="Q1", start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 31), **fields(self.tenant)
        )
        response = self.client.post("/api/accounting/fiscalperiods/", {
            "name": "Feb", "start_date": "2026-02-01", "end_date": "2026-02-28",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "overlapping_period")

    def test_account_with_postings_cannot_be_deleted(self):
        e = entry(self.tenant, self.journal, [(self.cash, "1", "0"), (self.revenue, "0", "1")])
        services.post_entry(entry=e, user=self.tenant["user"])
        self.assertEqual(self.client.delete(f"/api/accounting/accounts/{self.cash.id}/").status_code, 409)


class TenantAndPermissionTests(TestCase):

    def setUp(self):
        self.a = bootstrap_tenant("acc-a", modules=("accounting",), extra_permissions=ACTIONS)
        self.b = bootstrap_tenant("acc-b", modules=("accounting",), extra_permissions=ACTIONS)
        self.cash_a, self.revenue_a, _g, self.journal_a = chart(self.a)
        self.entry_a = entry(self.a, self.journal_a, [(self.cash_a, "50", "0"), (self.revenue_a, "0", "50")])
        services.post_entry(entry=self.entry_a, user=self.a["user"])

    def test_entity_isolation(self):
        client_b = self.b["client"]
        self.assertEqual(client_b.get("/api/accounting/accounts/").data["count"], 0)
        self.assertEqual(client_b.get(f"/api/accounting/journalentries/{self.entry_a.id}/").status_code, 404)
        self.assertEqual(client_b.post(f"/api/accounting/journalentries/{self.entry_a.id}/reverse/").status_code, 404)
        self.assertEqual(client_b.get("/api/accounting/accounts/trial_balance/").data["rows"], [])

    def test_another_entitys_account_or_journal_cannot_be_used(self):
        client_b = self.b["client"]
        response = client_b.post("/api/accounting/journalentries/", {
            "journal": str(self.journal_a.id), "date": "2026-01-01", "description": "x",
        }, format="json")
        self.assertEqual(response.status_code, 400)

        _c, _r, _g, journal_b = chart(self.b)
        e = entry(self.b, journal_b, [])
        response = client_b.post("/api/accounting/journalentrylines/", {
            "entry": str(e.id), "account": str(self.cash_a.id), "debit": "1", "credit": "0",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_module_inactive_is_403(self):
        tenant = bootstrap_tenant("acc-off")
        self.assertEqual(tenant["client"].get("/api/accounting/accounts/").status_code, 403)

    def test_posting_needs_its_permission(self):
        from django.contrib.auth.models import Permission

        from django_resaas.saas.core.tenant.context import ResaasContextService
        from django_resaas.saas.models.branch_user_group import BranchUserGroup
        from django_resaas.saas.models.group import Group

        tenant = bootstrap_tenant("acc-perm", modules=("accounting",))
        group = Group.objects.create(name="Accounting without post")
        group.permissions.set(
            Permission.objects.filter(content_type__app_label="accounting").exclude(codename="post_entry_journalentry")
        )
        BranchUserGroup.objects.create(branch=tenant["branch"], user=tenant["user"], group=group)
        issued = ResaasContextService.issue(
            user=tenant["user"], entity_id=tenant["entity"].id, branch_id=tenant["branch"].id, group_id=group.id
        )
        tenant["client"].credentials(HTTP_X_RESAAS_CONTEXT=issued["token"], HTTP_L="1")

        cash, revenue, _g, journal = chart(tenant)
        e = entry(tenant, journal, [(cash, "1", "0"), (revenue, "0", "1")])
        self.assertEqual(tenant["client"].get(f"/api/accounting/journalentries/{e.id}/").status_code, 200)
        self.assertEqual(tenant["client"].post(f"/api/accounting/journalentries/{e.id}/post/").status_code, 403)


class PostingRuleTests(TestCase):
    """Events with an amount become posted entries when the Entity has an
    active rule - once per source, reversed when a sale is cancelled."""

    def setUp(self):
        self.tenant = bootstrap_tenant("acc-rule", modules=("accounting",))
        self.cash, self.revenue, _g, self.journal = chart(self.tenant)
        PostingRule.objects.create(
            event=PostingRule.EVENT_SALE_CONFIRMED, journal=self.journal,
            debit_account=self.cash, credit_account=self.revenue, **fields(self.tenant)
        )

    def _emit(self, event, pk="00000000-0000-0000-0000-000000000001", amount="80.00", entity=None):
        """Delivers the payload EventDispatcher would build for a sale, to the
        listeners accounting registered (by event name, as in production)."""
        import fnmatch

        payload = {
            "event": event, "entity_id": str((entity or self.tenant["entity"]).id),
            "branch_id": str(self.tenant["branch"].id), "actor_id": str(self.tenant["user"].id),
            "object": {"app_label": "sales", "model": "sale", "pk": pk}, "context": {"amount": amount},
        }
        for pattern, listener, _propagate in list(EventDispatcher._listeners):
            if fnmatch.fnmatchcase(event, pattern) and listener.__module__ == "accounting.listeners":
                listener(payload)

    def test_event_posts_once(self):
        self._emit(PostingRule.EVENT_SALE_CONFIRMED)
        self._emit(PostingRule.EVENT_SALE_CONFIRMED)

        entries = JournalEntry.objects.filter(source_event=PostingRule.EVENT_SALE_CONFIRMED)
        self.assertEqual(entries.count(), 1)
        e = entries.get()
        self.assertEqual(e.status, JournalEntry.STATUS_POSTED)
        self.assertEqual(e.lines.get(account=self.cash).debit, Decimal("80.00"))
        self.assertEqual(e.lines.get(account=self.revenue).credit, Decimal("80.00"))

    def test_cancelled_sale_reverses_its_entry(self):
        self._emit(PostingRule.EVENT_SALE_CONFIRMED)
        self._emit("sales.sale.cancelled")

        original = JournalEntry.objects.get(source_event=PostingRule.EVENT_SALE_CONFIRMED)
        self.assertEqual(original.status, JournalEntry.STATUS_REVERSED)
        self.assertTrue(JournalEntry.objects.filter(reversal_of=original, status="posted").exists())

    def test_nothing_without_rule_amount_or_module(self):
        self._emit(PostingRule.EVENT_SALE_PAYMENT)
        self._emit(PostingRule.EVENT_SALE_CONFIRMED, pk="00000000-0000-0000-0000-000000000002", amount="0")
        other = bootstrap_tenant("acc-rule-off")
        self._emit(PostingRule.EVENT_SALE_CONFIRMED, pk="00000000-0000-0000-0000-000000000003", entity=other["entity"])
        self.assertFalse(JournalEntry.objects.exists())


class SalesIntegrationTests(TestCase):
    """End to end through the real sales service: confirming and cancelling a
    sale posts and reverses the entry; sales keeps working without accounting."""

    def test_sale_confirm_and_cancel(self):
        from sales import services as sales_services
        from sales.tests.helpers import make_customer, make_sale, make_sale_item
        import uuid

        tenant = bootstrap_tenant("acc-sales", modules=("accounting", "sales"))
        cash, revenue, _g, journal = chart(tenant)
        PostingRule.objects.create(
            event=PostingRule.EVENT_SALE_CONFIRMED, journal=journal,
            debit_account=cash, credit_account=revenue, **fields(tenant)
        )
        sale = make_sale(tenant, make_customer(tenant))
        make_sale_item(tenant, sale, product_id=uuid.uuid4(), quantidade=Decimal("2"), preco_unitario=Decimal("15"))
        sales_services.recalculate_totals(sale)

        sales_services.confirm_sale(sale=sale, user=tenant["user"])
        e = JournalEntry.objects.get(source_event="sales.sale.confirmed", source_id=str(sale.id))
        self.assertEqual(e.lines.get(account=revenue).credit, Decimal("30.00"))

        sales_services.cancel_sale(sale=sale, user=tenant["user"])
        e.refresh_from_db()
        self.assertEqual(e.status, JournalEntry.STATUS_REVERSED)

    def test_sales_without_accounting_module(self):
        from sales import services as sales_services
        from sales.tests.helpers import make_customer, make_sale, make_sale_item
        import uuid

        tenant = bootstrap_tenant("acc-sales-off", modules=("sales",))
        sale = make_sale(tenant, make_customer(tenant))
        make_sale_item(tenant, sale, product_id=uuid.uuid4())
        sales_services.recalculate_totals(sale)
        sales_services.confirm_sale(sale=sale, user=tenant["user"])
        self.assertFalse(JournalEntry.objects.exists())
