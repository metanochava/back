"""Small query helper other hr (and future rh) modules can call to check
whether a given date is a holiday for an Entity/Branch, without each
caller re-deriving the recurring-vs-fixed-date matching logic. No state,
no side effects - Fase 3 (Leave) is the first expected caller."""

from django.db.models import Q

from hr.models.holiday import Holiday


def is_holiday(entity, branch, date):
    """True if `date` is a holiday for `entity` (optionally scoped further
    by `branch`). Matches:

    - a fixed-date holiday (is_recurring=False) on the exact date, or
    - a recurring holiday (is_recurring=True, e.g. Christmas) on the same
      month/day in any year;

    and, for branch scoping: is_entity_wide=True rows (any branch of the
    entity) OR rows whose own `branch` equals the one asked about.
    """

    branch_filter = Q(is_entity_wide=True)

    if branch is not None:
        branch_filter |= Q(branch=branch)

    fixed = Q(is_recurring=False, date=date)
    recurring = Q(is_recurring=True, date__month=date.month, date__day=date.day)

    return (
        Holiday.objects
        .filter(entity=entity)
        .filter(branch_filter)
        .filter(fixed | recurring)
        .exists()
    )
