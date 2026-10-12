# The `accounting` module

`accounting` (`back/accounting`) is a double-entry general ledger: **chart of
accounts**, **journals**, **fiscal periods**, **journal entries** (draft →
posted → reversed), the **trial balance**, and **posting rules** that turn
business events of other modules into entries automatically.

It is a horizontal module. `sales` and `purchases` do not depend on it and do
not import it: they emit events, and accounting reacts to them by name when it
is active for the Entity and a rule exists.

> It is a ledger, not a statutory/fiscal accounting product. No country's chart
> of accounts, tax return or legal report format is implemented or claimed.

- `MY_APPS`: `'accounting'`; activated per Entity by Root (App catalogue /
  `EntityApp`). Inactive → every endpoint answers `403` and no automatic entry is
  posted.
- API: `/api/accounting/<resource>/`, all `BaseAPIView` (PROTECTED).

## Models

| Model | What it is |
|---|---|
| `Account` | `code` (unique per Entity), `name`, `account_type` (`asset`, `liability`, `equity`, `income`, `expense`), `parent` (tree), `allow_posting` (grouping accounts are `false`), `active`, `description`. |
| `Journal` | `code` (unique per Entity, prefixes entry numbers), `name`, `journal_type` (`general`, `sales`, `purchases`, `cash`, `bank`), `active`. |
| `FiscalPeriod` | `name`, `start_date`, `end_date` (no overlap per Entity), `status` (`open`/`closed`), `closed_at`/`closed_by`. |
| `JournalEntry` | `journal`, `number` (set when posted: `<journal code>-<year>-<sequence>`), `date`, `description`, `reference`, `status` (`draft`, `posted`, `reversed`), `posted_at`/`posted_by`, `reversal_of`, `source_event`/`source_id` (automatic entries). |
| `JournalEntryLine` | `entry`, `account`, `description`, `debit`, `credit` - exactly one of them > 0 (database check constraint). |
| `PostingRule` | `event`, `journal`, `debit_account`, `credit_account`, `active`; one per event and Entity. |

## Rules (enforced in `accounting/services.py`)

Posting an entry (`POST /journalentries/{id}/post/`) requires:

- at least two lines (`400 journal_entry_too_few_lines`);
- total debit = total credit > 0 (`400 journal_entry_unbalanced`);
- every account of the Entity, active and `allow_posting` (`400 account_not_postable`);
- an active journal of the Entity (`400 invalid_journal`);
- **periods:** if the Entity has fiscal periods, the date must be inside one
  (`400 no_fiscal_period`) that is open (`409 fiscal_period_closed`). An Entity
  without periods can post any date.

Then the entry is numbered under a row lock (a numbering race retries) and is
**immutable**: changing or deleting it, or any of its lines, answers
`409 journal_entry_not_draft`. A posted entry is corrected with
`POST /journalentries/{id}/reverse/` (`{"date"?, "description"?}`): a new posted
entry with debit and credit swapped, `reversal_of` pointing to the original,
which becomes `reversed`. A reversal cannot be reversed; nothing is deleted.

Fiscal periods: `close` refuses while draft entries are dated inside the period
(`409 fiscal_period_has_drafts`); a closed period cannot be edited or deleted;
`reopen` makes it postable again.

## Trial balance

`GET /api/accounting/accounts/trial_balance/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`
(permission `trial_balance_account`), current Entity only:

```json
{
  "date_from": "2026-01-01", "date_to": null,
  "rows": [{"account": "<id>", "code": "11", "name": "Cash", "account_type": "asset",
            "debit": "140.00", "credit": "0.00", "balance": "140.00"}],
  "total_debit": "140.00", "total_credit": "140.00"
}
```

Posted and reversed entries count (an entry and its reversal net to zero);
drafts do not. `balance` is signed by the account's normal side (assets and
expenses: debit - credit; the others: credit - debit).

## Automatic entries (posting rules)

`accounting/apps.py` registers listeners on `EventDispatcher` for the events of
`PostingRule.EVENT_CHOICES`:

| Event | Emitted by | `context.amount` |
|---|---|---|
| `purchases.receipt.posted` | `purchases.services.receive_order` | received quantity × unit cost |
| `sales.sale.confirmed` | `sales.services.confirm_sale` | sale total |
| `sales.payment.received` | `sales.services.add_payment` | payment amount |

When the Entity has `accounting` active and an **active rule** for the event,
an entry is created and posted for the amount: debit `debit_account`, credit
`credit_account`, in the rule's journal, dated today, with
`source_event`/`source_id` = the event and the object's id. That pair is unique
per Entity, so a repeated event never posts twice. `sales.sale.cancelled`
reverses the entry posted for that sale's `sales.sale.confirmed`.

Example (configured in **Posting rules**): event *Sale confirmed*, journal
`SAL`, debit `21 Customers`, credit `71 Sales revenue`.

A listener failure (no open period, an inactive account) is logged and does not
block the sale or the receipt (`propagate=False`); the entry can be made by
hand. To add an event: it must carry `context.amount` and an object, then add it
to `PostingRule.EVENT_CHOICES` (and translations).

## API and permissions

| Route | Permissions |
|---|---|
| `/accounts/`, `/journals/`, `/fiscalperiods/`, `/postingrules/` | `list_` / `view_` / `add_` / `change_` / `delete_<model>` |
| `/journalentries/`, `/journalentrylines/` (`?entry=<id>`) | idem; changes only while draft |
| `POST /journalentries/{id}/post/` | `post_entry_journalentry` |
| `POST /journalentries/{id}/reverse/` | `reverse_journalentry` |
| `POST /fiscalperiods/{id}/close/` · `/reopen/` | `close_fiscalperiod` · `reopen_fiscalperiod` |
| `GET /accounts/trial_balance/` | `trial_balance_account` |

Profiles (`accounting/profiles.py`, additive, same names as sales/purchases):
**Accountant** (accounts, journals, entries, post, reverse), **Finance Manager**
(periods and their close/reopen, posting rules, reverse), **Treasurer** and
**Auditor** (read and trial balance). Root gets the action permissions in
`accounting/signals.py`.

## Multi-tenancy

Everything is scoped to the current Entity by `BaseAPIView`; another Entity's
id answers `404`. A journal, account or entry of another Entity is refused on
write by `TenantRelationsMixin` (`400`), and posting checks again that every
line's account belongs to the entry's Entity. Automatic entries use the Entity
of the event payload.

## Frontend (`front/src/pages/accounting`)

- Chart of accounts, journals, fiscal periods (close/reopen from the row
  actions), posting rules: `s-auto-crud` (`AccountingCrudPage.vue`).
- Journal entries: list with **New journal entry**, and the entry page with its
  lines (add/remove while draft, live debit/credit totals), **Post** (enabled
  when balanced - the backend still validates) and **Reverse**.
- Trial balance: date filters, totals row.

## Tests

`accounting/tests`: posting and immutability, balance and line rules, grouping
accounts, reversal, trial balance by dates, periods (closed, missing,
overlapping, drafts), Entity isolation, module inactive, permission per action,
posting rules (once per source, reversal on cancellation, no rule/amount/module)
and end to end with `sales`; translations.

## Not implemented yet

Opening balances / year-end closing entries, multi-currency, cost centres,
financial statements (balance sheet, income statement), supplier invoices and
accounts payable, tax accounts.
