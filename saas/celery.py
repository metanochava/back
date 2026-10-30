# Celery app of this project (django_resaas docs/features/notifications.md,
# "Wiring Celery + Beat in a host project"). The notifications outbox
# (django_resaas.notifications.tasks) binds to it through @shared_task.
# Broker: CELERY_BROKER_URL (the local Redis); a worker and Beat run as the
# systemd units celery_<env>_worker / celery_<env>_beat.
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saas.settings")

app = Celery("saas")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "notifications-dispatch-pending": {
        "task": "django_resaas.notifications.dispatch_pending_notifications",
        "schedule": 30.0,  # OUTBOX_RECOVERY_INTERVAL_SECONDS
    },
    "notifications-recover-stuck": {
        "task": "django_resaas.notifications.recover_stuck_notifications",
        "schedule": 60.0,
    },
    "notifications-cleanup": {
        "task": "django_resaas.notifications.cleanup_notifications",
        "schedule": 86400.0,  # daily
    },
}
