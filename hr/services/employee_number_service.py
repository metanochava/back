from django.db import transaction
from django.utils import timezone


class EmployeeNumberService:
    """Generates the next employee number for an Entity, safely under
    concurrency.

    Format: EMP-<year>-<6-digit sequence>, sequence reset per Entity per
    year. select_for_update() locks the candidate rows for the duration
    of the caller's transaction.atomic() block, so two concurrent
    requests generating a number for the same Entity serialize instead
    of computing the same "next" value twice - the second one waits for
    the first's transaction to commit (or roll back) before it can read
    the now-updated last row.

    Caller is responsible for wrapping the generate() + Employee.save()
    in the same transaction.atomic() block - the lock only holds for
    the life of that transaction.
    """

    PREFIX = "EMP"

    @classmethod
    def generate(cls, entity):
        from hr.models.employee import Employee

        year = timezone.now().year
        year_prefix = f"{cls.PREFIX}-{year}-"

        last = (
            Employee.all_objects
            .select_for_update()
            .filter(entity=entity, code__startswith=year_prefix)
            .order_by("-code")
            .first()
        )

        next_seq = 1

        if last and last.code:
            try:
                next_seq = int(last.code.rsplit("-", 1)[-1]) + 1
            except ValueError:
                next_seq = (
                    Employee.all_objects
                    .filter(entity=entity, code__startswith=year_prefix)
                    .count()
                    + 1
                )

        return f"{year_prefix}{next_seq:06d}"
