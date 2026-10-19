"""Records as expired the online orders whose hold ended (run periodically,
e.g. from cron every 15 minutes). Stock is already free at expires_at - the
reservation stops holding it by itself; this only writes the order's status
and closes the reservation rows. Idempotent.

    python manage.py expire_online_orders
"""
from django.core.management.base import BaseCommand

from farmacia import online_order_service


class Command(BaseCommand):
    help = "Marks reserved online orders past their hold as expired and releases their reservations."

    def handle(self, *args, **options):
        count = online_order_service.expire_due()
        self.stdout.write(self.style.SUCCESS(f"Online orders expired: {count}"))
