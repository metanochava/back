"""Accounting reacts to business events by name only - it never imports
sales or purchases. Each listener runs inside the emitting transaction and
fails closed for accounting (propagate=False): a missing rule or a closed
period is logged and the business operation still completes; the entry can
then be posted by hand."""

from django_resaas.saas.models.user import User


def _actor(payload):
    actor_id = payload.get("actor_id")
    return User.objects.filter(id=actor_id).first() if actor_id else None


def on_event_with_amount(payload):
    from accounting import services

    services.post_from_event(payload, user=_actor(payload))


def on_sale_cancelled(payload):
    from accounting import services
    from accounting.models import PostingRule

    services.reverse_from_event(payload, PostingRule.EVENT_SALE_CONFIRMED, user=_actor(payload))
