"""
Service layer of crm: lead lifecycle, conversion into an opportunity, moving
opportunities through the pipeline, activities and the pipeline summary.

crm does not require sales: a customer is a loose sales.Customer id checked
through sales.services when the app is installed.
"""

from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException
from django_resaas.saas.models.entity_user import EntityUser

from crm.models import Activity, Lead, Opportunity, Stage

DEFAULT_STAGES = (
    ("Prospecting", 10, 10, False, False),
    ("Qualification", 20, 25, False, False),
    ("Proposal", 30, 50, False, False),
    ("Negotiation", 40, 75, False, False),
    ("Won", 50, 100, True, False),
    ("Lost", 60, 0, False, True),
)

LEAD_TRANSITIONS = {
    Lead.STATUS_NEW: {Lead.STATUS_CONTACTED, Lead.STATUS_QUALIFIED, Lead.STATUS_DISQUALIFIED},
    Lead.STATUS_CONTACTED: {Lead.STATUS_QUALIFIED, Lead.STATUS_DISQUALIFIED},
    Lead.STATUS_QUALIFIED: {Lead.STATUS_CONVERTED, Lead.STATUS_DISQUALIFIED},
    Lead.STATUS_DISQUALIFIED: {Lead.STATUS_NEW},
    Lead.STATUS_CONVERTED: set(),
}


def _invalid(message, code, details=None):
    return ResaasAPIException(message, code=code, details=details, status_code=status.HTTP_400_BAD_REQUEST)


# =========================================================
# VALIDATION OF REFERENCES
# =========================================================

def validate_user(user, entity_id, field):
    """An owner / assignee must be a user of the Entity."""
    if user is not None and not EntityUser.objects.filter(entity_id=entity_id, user=user).exists():
        raise _invalid("Does not belong to the current entity.", code="invalid_user", details={
            field: ["Does not belong to the current entity."]
        })


def validate_customer(customer_id, entity_id):
    if not customer_id:
        return
    snapshot = None
    if apps.is_installed("sales"):
        from sales import services as sales_services

        snapshot = sales_services.get_customer_snapshot(customer_id, entity_id)
    if snapshot is None:
        raise _invalid("Does not belong to the current entity.", code="invalid_customer", details={
            "customer_id": ["Does not belong to the current entity."]
        })


def customer_name(customer_id, entity_id):
    if not customer_id or not apps.is_installed("sales"):
        return None
    from sales import services as sales_services

    snapshot = sales_services.get_customer_snapshot(customer_id, entity_id)
    return snapshot["name"] if snapshot else None


# =========================================================
# STAGES
# =========================================================

@transaction.atomic
def create_default_stages(*, entity_id, branch_id, user):
    """The six usual stages, for an Entity that has none yet (409 otherwise)."""
    if Stage.objects.filter(entity_id=entity_id).exists():
        raise ConflictError("The pipeline already has stages.", code="stages_exist")
    return [
        Stage.objects.create(
            name=name, order=order, probability=probability, is_won=won, is_lost=lost,
            state="Active", entity_id=entity_id, branch_id=branch_id, created_by=user, updated_by=user,
        )
        for name, order, probability, won, lost in DEFAULT_STAGES
    ]


# =========================================================
# LEADS
# =========================================================

@transaction.atomic
def change_lead_status(*, lead, user, new_status, reason=None):
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    if new_status not in LEAD_TRANSITIONS.get(lead.status, set()) or new_status == Lead.STATUS_CONVERTED:
        raise ConflictError("This change is not allowed in the current status of the lead.", code="invalid_lead_transition",
                            details={"status": lead.status, "target": new_status})

    if new_status == Lead.STATUS_DISQUALIFIED:
        reason = (reason or "").strip()
        if not reason:
            raise _invalid("A reason is required.", code="reason_required", details={"reason": ["A reason is required."]})
        lead.disqualify_reason = reason

    lead.status = new_status
    lead.updated_by = user
    lead.save(update_fields=["status", "disqualify_reason", "updated_by", "updated_at"])
    return lead


@transaction.atomic
def convert_lead(*, lead, user, title=None, amount=None, stage=None, customer_id=None, expected_close_date=None):
    """A qualified (or new/contacted) lead becomes an open Opportunity in the
    first open stage (or the one given); the lead is marked converted."""
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    if lead.status in (Lead.STATUS_CONVERTED, Lead.STATUS_DISQUALIFIED):
        raise ConflictError("This lead cannot be converted.", code="lead_not_convertible", details={"status": lead.status})

    if stage is None:
        stage = Stage.objects.filter(entity_id=lead.entity_id, active=True, is_won=False, is_lost=False).first()
    if stage is None or stage.entity_id != lead.entity_id:
        raise _invalid("Create the pipeline stages first.", code="no_open_stage")
    if stage.is_won or stage.is_lost:
        raise _invalid("Choose an open stage.", code="stage_not_open", details={"stage": ["Choose an open stage."]})

    validate_customer(customer_id, lead.entity_id)

    opportunity = Opportunity.objects.create(
        title=title or lead.display_name,
        lead=lead,
        customer_id=customer_id or None,
        stage=stage,
        amount=Decimal(str(amount or 0)),
        expected_close_date=expected_close_date,
        owner=lead.owner or user,
        state="Active",
        entity_id=lead.entity_id,
        branch_id=lead.branch_id,
        created_by=user,
        updated_by=user,
    )

    lead.status = Lead.STATUS_CONVERTED
    lead.updated_by = user
    lead.save(update_fields=["status", "updated_by", "updated_at"])

    EventDispatcher.emit("crm.lead.converted", instance=lead, actor=user, context={"opportunity_id": str(opportunity.id)})
    return opportunity


# =========================================================
# OPPORTUNITIES
# =========================================================

@transaction.atomic
def move_opportunity(*, opportunity, user, stage, lost_reason=None):
    """Moves an open opportunity to another stage of its Entity. A won / lost
    stage closes it (a lost one needs a reason); a closed opportunity is
    reopened only by moving it back to an open stage."""
    opportunity = Opportunity.objects.select_for_update().get(pk=opportunity.pk)

    if stage.entity_id != opportunity.entity_id or not stage.active:
        raise _invalid("Does not belong to the current entity.", code="invalid_stage", details={
            "stage": ["Does not belong to the current entity."]
        })

    fields = ["stage", "status", "lost_reason", "closed_at", "updated_by", "updated_at"]
    event = None

    if stage.is_lost:
        lost_reason = (lost_reason or "").strip()
        if not lost_reason:
            raise _invalid("A reason is required.", code="reason_required", details={"lost_reason": ["A reason is required."]})
        opportunity.status, opportunity.lost_reason, opportunity.closed_at = Opportunity.STATUS_LOST, lost_reason, timezone.now()
        event = "crm.opportunity.lost"
    elif stage.is_won:
        opportunity.status, opportunity.lost_reason, opportunity.closed_at = Opportunity.STATUS_WON, None, timezone.now()
        event = "crm.opportunity.won"
    else:
        opportunity.status, opportunity.lost_reason, opportunity.closed_at = Opportunity.STATUS_OPEN, None, None

    previous = opportunity.stage_id
    opportunity.stage = stage
    opportunity.updated_by = user
    opportunity.save(update_fields=fields)

    if event and previous != stage.id:
        EventDispatcher.emit(event, instance=opportunity, actor=user, context={
            "amount": str(opportunity.amount),
            "customer_id": str(opportunity.customer_id) if opportunity.customer_id else None,
        })
    return opportunity


def pipeline_summary(entity_id, owner=None):
    """Open opportunities per active stage: count, amount and amount weighted
    by the stage's probability."""
    opportunities = Opportunity.objects.filter(entity_id=entity_id, status=Opportunity.STATUS_OPEN)
    if owner is not None:
        opportunities = opportunities.filter(owner=owner)

    totals = {
        row["stage"]: row
        for row in opportunities.values("stage").annotate(count=Count("id"), amount=Sum("amount"))
    }

    rows = []
    for stage in Stage.objects.filter(entity_id=entity_id, active=True, is_won=False, is_lost=False):
        amount = (totals.get(stage.id) or {}).get("amount") or Decimal("0")
        rows.append({
            "stage": str(stage.id),
            "name": stage.name,
            "probability": stage.probability,
            "count": (totals.get(stage.id) or {}).get("count") or 0,
            "amount": amount,
            "weighted_amount": (amount * stage.probability / Decimal("100")).quantize(Decimal("0.01")),
        })

    return {
        "stages": rows,
        "total_amount": sum((row["amount"] for row in rows), Decimal("0")),
        "total_weighted_amount": sum((row["weighted_amount"] for row in rows), Decimal("0")),
    }


# =========================================================
# ACTIVITIES
# =========================================================

@transaction.atomic
def complete_activity(*, activity, user):
    activity = Activity.objects.select_for_update().get(pk=activity.pk)
    if activity.completed_at is not None:
        raise ConflictError("This activity is already done.", code="activity_done")
    activity.completed_at = timezone.now()
    activity.updated_by = user
    activity.save(update_fields=["completed_at", "updated_by", "updated_at"])
    return activity
