"""
Service layer of accounting: posting and reversing entries, periods, the
trial balance and the automatic entries made from business events. Views
only validate input and call these functions.

Invariants enforced here (and only here):
- a posted entry has >= 2 lines, every line on a postable, active account of
  the same Entity, total debit == total credit > 0;
- when the Entity has fiscal periods, its date is inside an OPEN one;
- a posted entry is never edited or deleted - it is corrected by a reversal;
- an event (source_event, source_id) posts at most once per Entity.
"""

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException

from accounting.models import Account, FiscalPeriod, JournalEntry, JournalEntryLine, PostingRule

ZERO = Decimal("0")


def _invalid(message, code, details=None):
    return ResaasAPIException(message, code=code, details=details, status_code=status.HTTP_400_BAD_REQUEST)


def assert_draft(entry):
    if entry.status != JournalEntry.STATUS_DRAFT:
        raise ConflictError("A posted journal entry cannot be changed.", code="journal_entry_not_draft")


# =========================================================
# PERIODS
# =========================================================

def period_for(entity_id, date):
    """(has_periods, the period containing date or None)."""
    periods = FiscalPeriod.objects.filter(entity_id=entity_id)
    if not periods.exists():
        return False, None
    return True, periods.filter(start_date__lte=date, end_date__gte=date).first()


def assert_open_date(entity_id, date):
    has_periods, period = period_for(entity_id, date)
    if not has_periods:
        return
    if period is None:
        raise _invalid("There is no fiscal period for this date.", code="no_fiscal_period", details={"date": [
            "There is no fiscal period for this date."
        ]})
    if period.status != FiscalPeriod.STATUS_OPEN:
        raise ConflictError("The fiscal period of this date is closed.", code="fiscal_period_closed")


def validate_period_dates(entity_id, start_date, end_date, exclude_pk=None):
    if start_date and end_date and start_date > end_date:
        raise _invalid("The end date must be after the start date.", code="invalid_period", details={
            "end_date": ["The end date must be after the start date."]
        })
    overlapping = FiscalPeriod.objects.filter(entity_id=entity_id, start_date__lte=end_date, end_date__gte=start_date)
    if exclude_pk:
        overlapping = overlapping.exclude(pk=exclude_pk)
    if overlapping.exists():
        raise _invalid("This period overlaps another fiscal period.", code="overlapping_period", details={
            "start_date": ["This period overlaps another fiscal period."]
        })


@transaction.atomic
def close_period(*, period, user):
    period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status == FiscalPeriod.STATUS_CLOSED:
        raise ConflictError("The fiscal period is already closed.", code="fiscal_period_closed")
    drafts = JournalEntry.objects.filter(
        entity_id=period.entity_id, status=JournalEntry.STATUS_DRAFT,
        date__gte=period.start_date, date__lte=period.end_date,
    )
    if drafts.exists():
        raise ConflictError(
            "Post or delete the draft entries of this period before closing it.",
            code="fiscal_period_has_drafts",
            details={"drafts": drafts.count()},
        )
    period.status = FiscalPeriod.STATUS_CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user
    period.updated_by = user
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_by", "updated_at"])
    return period


@transaction.atomic
def reopen_period(*, period, user):
    period = FiscalPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status == FiscalPeriod.STATUS_OPEN:
        raise ConflictError("The fiscal period is already open.", code="fiscal_period_open")
    period.status = FiscalPeriod.STATUS_OPEN
    period.closed_at = None
    period.closed_by = None
    period.updated_by = user
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_by", "updated_at"])
    return period


# =========================================================
# POSTING
# =========================================================

def next_number(entry):
    prefix = f"{entry.journal.code}-{entry.date.year}-"
    last = (
        JournalEntry.all_objects.filter(entity_id=entry.entity_id, number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    sequence = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


def validate_lines(entry, lines):
    if len(lines) < 2:
        raise _invalid("A journal entry needs at least two lines.", code="journal_entry_too_few_lines")

    debit = sum((line.debit for line in lines), ZERO)
    credit = sum((line.credit for line in lines), ZERO)

    for line in lines:
        account = line.account
        if account.entity_id != entry.entity_id:
            raise _invalid("Does not belong to the current entity.", code="invalid_account")
        if not account.allow_posting or not account.active:
            raise _invalid(
                "This account does not accept postings.",
                code="account_not_postable",
                details={"account": account.display_name},
            )

    if debit <= ZERO or debit != credit:
        raise _invalid(
            "The journal entry is not balanced: total debit must equal total credit.",
            code="journal_entry_unbalanced",
            details={"debit": str(debit), "credit": str(credit)},
        )


@transaction.atomic
def post_entry(*, entry, user, attempts=3):
    entry = JournalEntry.objects.select_for_update().select_related("journal").get(pk=entry.pk)
    assert_draft(entry)

    if entry.journal.entity_id != entry.entity_id or not entry.journal.active:
        raise _invalid("This journal cannot be used.", code="invalid_journal")

    lines = list(entry.lines.select_related("account"))
    validate_lines(entry, lines)
    assert_open_date(entry.entity_id, entry.date)

    for attempt in range(attempts):
        try:
            with transaction.atomic():
                entry.number = next_number(entry)
                entry.status = JournalEntry.STATUS_POSTED
                entry.posted_at = timezone.now()
                entry.posted_by = user
                entry.updated_by = user
                entry.save(update_fields=["number", "status", "posted_at", "posted_by", "updated_by", "updated_at"])
                return entry
        except IntegrityError:
            if attempt == attempts - 1:
                raise ConflictError("Could not number the journal entry, try again.", code="journal_entry_number_conflict")


@transaction.atomic
def reverse_entry(*, entry, user, date=None, description=None):
    """A new posted entry with every line's debit and credit swapped; the
    original becomes `reversed`. Nothing is deleted."""
    entry = JournalEntry.objects.select_for_update().select_related("journal").get(pk=entry.pk)

    if entry.status != JournalEntry.STATUS_POSTED:
        raise ConflictError("Only a posted journal entry can be reversed.", code="journal_entry_not_posted")
    if entry.reversal_of_id:
        raise ConflictError("A reversal entry cannot be reversed.", code="journal_entry_is_reversal")

    reversal = JournalEntry.objects.create(
        journal=entry.journal,
        date=date or timezone.localdate(),
        description=description or f"Reversal of {entry.number}",
        reference=entry.number,
        reversal_of=entry,
        state="Active",
        entity_id=entry.entity_id,
        branch_id=entry.branch_id,
        created_by=user,
        updated_by=user,
    )
    for line in entry.lines.all():
        JournalEntryLine.objects.create(
            entry=reversal,
            account_id=line.account_id,
            description=line.description,
            debit=line.credit,
            credit=line.debit,
            state="Active",
            entity_id=entry.entity_id,
            branch_id=entry.branch_id,
            created_by=user,
            updated_by=user,
        )

    post_entry(entry=reversal, user=user)

    entry.status = JournalEntry.STATUS_REVERSED
    entry.updated_by = user
    entry.save(update_fields=["status", "updated_by", "updated_at"])
    reversal.refresh_from_db()
    return reversal


# =========================================================
# TRIAL BALANCE
# =========================================================

def trial_balance(entity_id, date_from=None, date_to=None):
    """Debit / credit totals and balance per account, over POSTED and
    REVERSED entries (a reversal is itself posted, so the pair nets to zero).
    Balance is signed by the account's normal side."""
    lines = JournalEntryLine.objects.filter(
        entity_id=entity_id,
        entry__status__in=(JournalEntry.STATUS_POSTED, JournalEntry.STATUS_REVERSED),
    )
    if date_from:
        lines = lines.filter(entry__date__gte=date_from)
    if date_to:
        lines = lines.filter(entry__date__lte=date_to)

    totals = {
        row["account"]: row
        for row in lines.values("account").annotate(debit=Sum("debit"), credit=Sum("credit"))
    }

    rows = []
    for account in Account.objects.filter(id__in=totals.keys()).order_by("code"):
        debit = totals[account.id]["debit"] or ZERO
        credit = totals[account.id]["credit"] or ZERO
        rows.append({
            "account": str(account.id),
            "code": account.code,
            "name": account.name,
            "account_type": account.account_type,
            "debit": debit,
            "credit": credit,
            "balance": (debit - credit) if account.debit_normal else (credit - debit),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "total_debit": sum((row["debit"] for row in rows), ZERO),
        "total_credit": sum((row["credit"] for row in rows), ZERO),
    }


# =========================================================
# AUTOMATIC ENTRIES (POSTING RULES)
# =========================================================

def accounting_active(entity_id):
    from django_resaas.saas.models.entity_app import EntityApp

    return EntityApp.objects.filter(entity_id=entity_id, app__name="accounting", state="Active").exists()


def _amount(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount > ZERO else None


@transaction.atomic
def post_from_event(payload, user=None):
    """Creates and posts the entry of an event that has an active PostingRule
    for its Entity. Returns the entry, or None when there is nothing to post
    (module inactive, no rule, no amount, or already posted for that source)."""
    entity_id = payload.get("entity_id")
    event = payload.get("event")
    source = (payload.get("object") or {}).get("pk")
    amount = _amount((payload.get("context") or {}).get("amount"))

    if not (entity_id and event and source and amount) or not accounting_active(entity_id):
        return None

    rule = PostingRule.objects.filter(entity_id=entity_id, event=event, active=True).select_related(
        "journal", "debit_account", "credit_account"
    ).first()
    if rule is None:
        return None

    if JournalEntry.all_objects.filter(entity_id=entity_id, source_event=event, source_id=source).exists():
        return None

    context = payload.get("context") or {}
    common = dict(
        state="Active",
        entity_id=entity_id,
        branch_id=payload.get("branch_id"),
        created_by=user,
        updated_by=user,
    )
    try:
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                journal=rule.journal,
                date=timezone.localdate(),
                description=rule.get_event_display(),
                reference=context.get("reference"),
                source_event=event,
                source_id=source,
                **common,
            )
    except IntegrityError:
        return None  # a concurrent delivery of the same event won

    JournalEntryLine.objects.create(entry=entry, account=rule.debit_account, debit=amount, credit=ZERO, **common)
    JournalEntryLine.objects.create(entry=entry, account=rule.credit_account, debit=ZERO, credit=amount, **common)

    return post_entry(entry=entry, user=user)


@transaction.atomic
def reverse_from_event(payload, source_event, user=None):
    """Reverses the automatic entry posted for (source_event, object pk), if
    any - e.g. a cancelled sale reverses its 'sales.sale.confirmed' entry."""
    entity_id = payload.get("entity_id")
    source = (payload.get("object") or {}).get("pk")
    if not (entity_id and source) or not accounting_active(entity_id):
        return None

    entry = JournalEntry.objects.filter(
        entity_id=entity_id, source_event=source_event, source_id=source, status=JournalEntry.STATUS_POSTED,
    ).first()
    if entry is None:
        return None
    return reverse_entry(entry=entry, user=user)

