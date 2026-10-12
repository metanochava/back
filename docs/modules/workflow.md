# The `workflow` module (approvals)

`workflow` (`back/workflow`) runs **approval processes** configured per Entity:
a definition for one kind of object (e.g. purchase orders), ordered **steps**
decided by users who hold a given **permission**, and, when the last step is
approved, a **registered action** (e.g. approve the purchase order).

Nothing configured in the database is executed as code: a definition only
chooses one of the actions that modules registered in code.

- `MY_APPS`: `'workflow'`; activated per Entity by Root. Inactive → `403`, and
  nothing starts automatically.
- API: `/api/workflow/<resource>/` (`definitions`, `steps`, `instances`), all
  `BaseAPIView` (PROTECTED).

## Models

| Model | What it is |
|---|---|
| `WorkflowDefinition` | `name`, `code` (unique per Entity), `target_model` (`app_label.ModelName`, one of the models with registered actions), `on_approved_action` (registered action name), `start_event` (optional), `allow_self_approval` (default `false`), `active`. |
| `WorkflowStep` | `definition`, `order` (unique per definition), `name`, `approver_permission` (an existing permission codename), `required_approvals` (≥ 1). |
| `WorkflowInstance` | One approval request: `definition`, `target_model`, `object_id`, `object_label`, `current_step`, `status` (`pending`, `approved`, `rejected`, `cancelled`), `started_by`, `completed_at`. One `pending` instance per object and definition (database constraint). |
| `WorkflowDecision` | `instance`, `step`, `decided_by`, `decision` (`approve`/`reject`), `comment`; one per user and step (database constraint). |

## How an approval runs (`workflow/services.py`)

1. **Start** - `POST /instances/` (`{"definition", "object_id"}`), or by itself
   when a business event equal to `start_event` is emitted for an object of
   `target_model` (an `EventDispatcher` listener on `*`, in its own savepoint:
   a failure never breaks the emitting operation). The object must exist in the
   same Entity (`400 invalid_object`); a second pending instance is
   `409 workflow_already_pending`. Event `workflow.instance.started`.
2. **Decide** - `POST /instances/{id}/decide/` (`{"decision", "comment"}`). The
   user must hold the current step's `approver_permission` in the **active
   profile of the signed context** (`held_codenames()` - effective permissions,
   never a group name; `403 not_an_approver`), may not be the starter unless
   `allow_self_approval` (`403 self_approval`), and decides a step once
   (`409 already_decided`). A rejection needs a comment.
   - `required_approvals` approvals from distinct users move to the next step;
   - one rejection ends the instance as `rejected`;
   - after the last step the instance is `approved`.
3. **Finish** - the registered action's `on_approved` (or `on_rejected`) runs
   **in the decision's transaction**: if it fails (e.g. the object changed
   status meanwhile), the decision is not recorded and the error is answered.
   Events `workflow.instance.approved` / `workflow.instance.rejected`.
4. **Cancel** - `POST /instances/{id}/cancel/`: by the starter, or by holders
   of `cancel_any_workflowinstance`.

**Inbox** - `GET /instances/inbox/`: the pending instances the current user can
decide now (holds the step's permission, did not start it, has not decided
it). Each instance also carries `can_decide` for the current user.

## Registering an action (module side)

```python
# purchases/apps.py - only when the workflow app is installed
from django.apps import apps

if apps.is_installed("workflow"):
    from workflow.registry import register_action

    register_action(
        "purchases.approve_order",
        label="Approve the purchase order",
        model="purchases.PurchaseOrder",
        on_approved=lambda order, user: services.approve_order(order=order, user=user),
        on_rejected=lambda order, user: services.return_to_draft(order=order, user=user),
    )
```

Handlers receive the object (looked up inside the instance's Entity) and the
deciding user, and must use the module's own services (state machine, locks,
audit). A definition's `on_approved_action` must be registered **for its
`target_model`** (`400 invalid_workflow_action`).

### Example: purchase order approval

Definition: target `purchases.PurchaseOrder`, action *Approve the purchase
order*, start event `purchases.order.submitted`; steps *Finance*
(`approve_purchaseorder`, 2 approvals) and *Director* (`approve_purchaseorder`).
Submitting an order starts the approval; while it is pending, the order's direct
**Approve** action answers `409 approval_workflow_pending`; the last approval
approves the order (`approved_by` = that approver); a rejection returns it to
draft.

## Permissions and profiles

CRUD on definitions/steps; `add_`/`view_`/`list_workflowinstance`,
`decide_workflowinstance`, `cancel_workflowinstance`, `inbox_workflowinstance`,
`cancel_any_workflowinstance`. Deciding a step **also** needs the step's own
permission. Profiles (`workflow/profiles.py`): **Admin** configures workflows;
Purchasing Manager, Finance Manager and Buyer use the inbox and decide; Auditor
reads.

## Multi-tenancy

Everything is the current Entity's (`404` for another Entity's instance); a
definition, step or object of another Entity cannot be used (`400`). Automatic
starts use the Entity of the event.

## Frontend (`front/src/pages/workflow`)

- **My approvals** (`view_approval_inbox`): what waits for my decision.
- **Approval request** page: workflow, current step, starter, decision timeline,
  **Approve** / **Reject** (shown when `can_decide`; reject asks for a reason),
  **Cancel**.
- Approval requests, workflows, workflow steps: `s-auto-crud`.

## Tests

`workflow/tests/test_workflow.py`: full approval with two steps and two
approvals running the purchase-order action, starter and non-holder refused,
once per step, rejection back to draft, one pending per object, cancel, inbox,
automatic start by event, definition/step validation, failing action undoes the
decision, tenant isolation, module inactive; translations.

## Not implemented yet

Notifications to approvers (to come through `django_resaas.notifications` on
`workflow.instance.started`), deadlines/escalation, conditional steps (e.g. by
amount), delegation.
