"""
Service layer of workflow (approval processes).

- start_instance(): an approval for one object of the definition's model, which
  must exist in the same Entity; one pending instance per object.
- decide(): the current step is decided by users holding its
  approver_permission in their ACTIVE profile (effective permissions, never a
  group name), once each; required_approvals approvals move to the next step,
  one rejection ends the instance. After the last step, the registered action
  (workflow.registry) runs in the same transaction - if it fails, the decision
  is not recorded.
- on_event(): definitions with start_event start by themselves when that
  business event is emitted for an object (EventDispatcher).
"""

import logging

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ConflictError, ResaasAPIException

from workflow import registry
from workflow.models import WorkflowDecision, WorkflowDefinition, WorkflowInstance

logger = logging.getLogger(__name__)


def _invalid(message, code, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    return ResaasAPIException(message, code=code, details=details, status_code=status_code)


# =========================================================
# DEFINITIONS
# =========================================================

def model_for(label):
    try:
        return apps.get_model(label)
    except (LookupError, ValueError):
        return None


def validate_definition(target_model, on_approved_action):
    """target_model must be an installed model with an Entity; the action, if
    any, must be registered for that model."""
    Model = model_for(target_model or "")
    if Model is None or not hasattr(Model, "entity_id"):
        raise _invalid("Choose an installed model of the Entity.", code="invalid_target_model", details={
            "target_model": ["Choose an installed model of the Entity."]
        })
    if on_approved_action:
        action = registry.get_action(on_approved_action)
        if action is None or action.model.lower() != f"{Model._meta.app_label}.{Model.__name__}".lower():
            raise _invalid("This action is not available for this model.", code="invalid_workflow_action", details={
                "on_approved_action": ["This action is not available for this model."]
            })


def target_choices():
    """Models that registered workflow actions (for the definition form)."""
    return sorted({(action.model, action.model) for action in registry.actions()})


# =========================================================
# INSTANCES
# =========================================================

def resolve_target(definition, object_id):
    Model = model_for(definition.target_model)
    if Model is None:
        return None
    try:
        with transaction.atomic():
            return Model.objects.filter(pk=object_id, entity_id=definition.entity_id).first()
    except (ValueError, TypeError, ValidationError, DatabaseError):  # not a valid pk of this model
        return None


@transaction.atomic
def start_instance(*, definition, object_id, user):
    if not definition.active:
        raise ConflictError("This workflow is not active.", code="workflow_inactive")

    first_step = definition.steps.order_by("order").first()
    if first_step is None:
        raise _invalid("The workflow has no steps.", code="workflow_without_steps")

    target = resolve_target(definition, object_id)
    if target is None:
        raise _invalid("Does not belong to the current entity.", code="invalid_object", details={
            "object_id": ["Does not belong to the current entity."]
        })

    try:
        with transaction.atomic():
            instance = WorkflowInstance.objects.create(
                definition=definition,
                target_model=definition.target_model,
                object_id=str(target.pk),
                object_label=str(target)[:255],
                current_step=first_step,
                started_by=user,
                state="Active",
                entity_id=definition.entity_id,
                branch_id=getattr(target, "branch_id", None) or definition.branch_id,
                created_by=user,
                updated_by=user,
            )
    except IntegrityError:
        raise ConflictError("An approval is already pending for this object.", code="workflow_already_pending")

    EventDispatcher.emit("workflow.instance.started", instance=instance, actor=user, context={
        "definition": definition.code, "object_id": instance.object_id,
    })
    return instance


def can_decide(instance, user, held):
    """(True, None) or (False, reason code) - for the UI and decide()."""
    if instance.status != WorkflowInstance.STATUS_PENDING or instance.current_step_id is None:
        return False, "workflow_not_pending"
    if instance.current_step.approver_permission not in held:
        return False, "not_an_approver"
    if not instance.definition.allow_self_approval and instance.started_by_id == user.id:
        return False, "self_approval"
    if instance.decisions.filter(step_id=instance.current_step_id, decided_by=user).exists():
        return False, "already_decided"
    return True, None


@transaction.atomic
def decide(*, instance, user, held, decision, comment=None):
    instance = (
        # lock only the instance row: current_step is a nullable (outer) join
        WorkflowInstance.objects.select_for_update(of=("self",))
        .select_related("definition", "current_step")
        .get(pk=instance.pk)
    )

    if decision not in (WorkflowDecision.DECISION_APPROVE, WorkflowDecision.DECISION_REJECT):
        raise _invalid("Choose approve or reject.", code="invalid_decision", details={"decision": ["Choose approve or reject."]})

    allowed, reason = can_decide(instance, user, held)
    if not allowed:
        if reason == "workflow_not_pending":
            raise ConflictError("This approval is no longer pending.", code=reason)
        if reason == "already_decided":
            raise ConflictError("You already decided this step.", code=reason)
        if reason == "self_approval":
            raise _invalid("You cannot decide an approval you started.", code=reason, status_code=status.HTTP_403_FORBIDDEN)
        raise _invalid("You are not an approver of this step.", code=reason, status_code=status.HTTP_403_FORBIDDEN)

    if decision == WorkflowDecision.DECISION_REJECT and not (comment or "").strip():
        raise _invalid("A reason is required.", code="reason_required", details={"comment": ["A reason is required."]})

    step = instance.current_step
    WorkflowDecision.objects.create(
        instance=instance, step=step, decided_by=user, decision=decision, comment=comment,
        state="Active", entity_id=instance.entity_id, branch_id=instance.branch_id,
        created_by=user, updated_by=user,
    )

    if decision == WorkflowDecision.DECISION_REJECT:
        _finish(instance, user, WorkflowInstance.STATUS_REJECTED)
        return instance

    approvals = instance.decisions.filter(step=step, decision=WorkflowDecision.DECISION_APPROVE).count()
    if approvals < step.required_approvals:
        return instance

    next_step = instance.definition.steps.filter(order__gt=step.order).order_by("order").first()
    if next_step is not None:
        instance.current_step = next_step
        instance.updated_by = user
        instance.save(update_fields=["current_step", "updated_by", "updated_at"])
        return instance

    _finish(instance, user, WorkflowInstance.STATUS_APPROVED)
    return instance


def _finish(instance, user, final_status):
    instance.status = final_status
    instance.current_step = None
    instance.completed_at = timezone.now()
    instance.updated_by = user
    instance.save(update_fields=["status", "current_step", "completed_at", "updated_by", "updated_at"])

    action = registry.get_action(instance.definition.on_approved_action or "")
    if action is not None:
        handler = action.on_approved if final_status == WorkflowInstance.STATUS_APPROVED else action.on_rejected
        if handler is not None:
            target = resolve_target(instance.definition, instance.object_id)
            if target is None:
                raise ConflictError("The object of this approval no longer exists.", code="workflow_object_missing")
            # runs in the decision's transaction: a failure undoes the decision
            handler(target, user)

    EventDispatcher.emit(f"workflow.instance.{final_status}", instance=instance, actor=user, context={
        "definition": instance.definition.code,
        "target_model": instance.target_model,
        "object_id": instance.object_id,
    })


@transaction.atomic
def cancel(*, instance, user, can_cancel_any):
    instance = WorkflowInstance.objects.select_for_update().get(pk=instance.pk)
    if instance.status != WorkflowInstance.STATUS_PENDING:
        raise ConflictError("This approval is no longer pending.", code="workflow_not_pending")
    if instance.started_by_id != user.id and not can_cancel_any:
        raise _invalid("Only who started it can cancel this approval.", code="not_the_starter",
                       status_code=status.HTTP_403_FORBIDDEN)
    instance.status = WorkflowInstance.STATUS_CANCELLED
    instance.current_step = None
    instance.completed_at = timezone.now()
    instance.updated_by = user
    instance.save(update_fields=["status", "current_step", "completed_at", "updated_by", "updated_at"])
    return instance


def inbox(*, entity_id, user, held):
    """Pending instances whose current step the user may decide now."""
    pending = (
        WorkflowInstance.objects.filter(
            entity_id=entity_id,
            status=WorkflowInstance.STATUS_PENDING,
            current_step__approver_permission__in=held,
        )
        .select_related("definition", "current_step")
        .order_by("created_at")
    )
    return [instance for instance in pending if can_decide(instance, user, held)[0]]


# =========================================================
# AUTOMATIC START (EVENTS)
# =========================================================

def on_event(payload):
    """EventDispatcher listener ("*"): starts the active definitions whose
    start_event is this event, for the event's object. Runs in a savepoint so a
    failure never breaks the emitting transaction."""
    entity_id = payload.get("entity_id")
    obj = payload.get("object") or {}
    if not (entity_id and obj.get("pk")) or payload.get("event", "").startswith("workflow."):
        return

    try:
        with transaction.atomic():
            definitions = list(WorkflowDefinition.objects.filter(
                entity_id=entity_id, start_event=payload["event"], active=True,
            ))
            if not definitions:
                return
            if not _module_active(entity_id):
                return

            from django_resaas.saas.models.user import User

            user = User.objects.filter(id=payload.get("actor_id")).first() if payload.get("actor_id") else None
            for definition in definitions:
                if model_for(definition.target_model)._meta.model_name != obj.get("model"):
                    continue
                try:
                    with transaction.atomic():
                        start_instance(definition=definition, object_id=obj["pk"], user=user)
                except (ConflictError, ResaasAPIException):
                    continue  # already pending, no steps, ...
    except Exception:
        logger.exception("workflow: automatic start failed for event %s", payload.get("event"))


def _module_active(entity_id):
    from django_resaas.saas.models.entity_app import EntityApp

    return EntityApp.objects.filter(entity_id=entity_id, app__name="workflow", state="Active").exists()
