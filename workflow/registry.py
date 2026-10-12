"""
The actions a workflow may run when an approval finishes. Only code can add
one (a module calls register_action() from its AppConfig.ready() when the
workflow app is installed); a workflow definition only CHOOSES one by name.
Nothing configured in the database is ever executed as code.

    register_action(
        "purchases.approve_order",
        label="Approve the purchase order",
        model="purchases.PurchaseOrder",
        on_approved=lambda obj, user: services.approve_order(order=obj, user=user),
    )
"""

from dataclasses import dataclass
from typing import Callable, Optional

_ACTIONS = {}


@dataclass(frozen=True)
class WorkflowAction:
    name: str
    label: str
    model: str  # "app_label.ModelName" of the objects it applies to
    on_approved: Callable
    on_rejected: Optional[Callable] = None


def register_action(name, *, label, model, on_approved, on_rejected=None):
    _ACTIONS[name] = WorkflowAction(name, label, model, on_approved, on_rejected)


def get_action(name):
    return _ACTIONS.get(name)


def action_choices():
    return sorted(((a.name, a.label) for a in _ACTIONS.values()), key=lambda c: c[1])


def actions():
    return list(_ACTIONS.values())
