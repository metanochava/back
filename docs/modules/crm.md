# The `crm` module

`crm` (`back/crm`) follows potential business from first contact to a won or
lost deal: **leads**, **opportunities** in a configurable **pipeline** of
stages, and **activities** (calls, e-mails, meetings, tasks, notes).

It is a horizontal module. It does not require `sales`: an opportunity can point
to a `sales.Customer` by a loose id, checked through `sales.services` only when
sales is installed.

- `MY_APPS`: `'crm'`; activated per Entity by Root. Inactive → `403`.
- API: `/api/crm/<resource>/` (`stages`, `leads`, `opportunities`,
  `activities`), all `BaseAPIView` (PROTECTED).

## Models

| Model | What it is |
|---|---|
| `Stage` | `name` (unique per Entity), `order`, `probability` (0-100), `is_won` / `is_lost` (not both), `active`. |
| `Lead` | `name`, `company_name`, `email`, `phone`, `source`, `status`, `owner` (a user of the Entity), `disqualify_reason`, `notes`. |
| `Opportunity` | `title`, `lead`, `customer_id` (loose `sales.Customer`), `stage`, `amount`, `expected_close_date`, `owner`, `status` (`open`/`won`/`lost`, from the stage), `lost_reason`, `closed_at`, `notes`. Read only: `customer_name`. |
| `Activity` | `activity_type`, `subject`, `lead` and/or `opportunity` (at least one - database check), `due_at`, `assigned_to`, `completed_at`, `notes`. |

## Workflow (`crm/services.py`)

**Stages.** `POST /stages/create_defaults/` creates Prospecting (10 %),
Qualification (25 %), Proposal (50 %), Negotiation (75 %), Won and Lost for an
Entity without stages (`409 stages_exist` otherwise). A stage with
opportunities cannot be deleted (`409 stage_in_use`): make it inactive.

**Leads.** `new → contacted → qualified → converted`, `disqualified` from any
open status (reason required), `reopen` back to `new`. Actions:
`mark_contacted`, `qualify`, `disqualify` (`{"reason"}`), `reopen`, `convert`.
`status` is read only in CRUD; a transition not allowed is
`409 invalid_lead_transition`.

**Convert** (`POST /leads/{id}/convert/`,
`{"title"?, "amount"?, "stage"?, "customer_id"?, "expected_close_date"?}`):
creates an open opportunity in the given or first open stage, owned by the
lead's owner (or the user), and marks the lead `converted`
(`409 lead_not_convertible` for a converted or disqualified lead). Event
`crm.lead.converted`.

**Opportunities.** The stage is chosen on creation (an open one) and changed
only with `POST /opportunities/{id}/move/` (`{"stage", "lost_reason"?}`):

- a won stage → `status=won`, `closed_at` set, event `crm.opportunity.won`
  (`context.amount`, `customer_id`);
- a lost stage → needs `lost_reason`, `status=lost`, event `crm.opportunity.lost`;
- an open stage → reopens (`status=open`, closing fields cleared).

**Pipeline** (`GET /opportunities/pipeline/?mine=true`): open opportunities per
active open stage - `count`, `amount`, `weighted_amount` (amount × probability)
- and the totals.

**Activities.** CRUD plus `POST /activities/{id}/complete/`
(`409 activity_done` the second time).

## Security and tenant scope

Every list/detail is the current Entity's; another Entity's id is `404`. Stage,
lead and opportunity references of another Entity are refused
(`TenantRelationsMixin` / explicit checks, `400`). `owner` and `assigned_to` must
be users of the Entity (`EntityUser`), `customer_id` one of its customers
(`400 invalid_customer`; always refused when sales is not installed).

Permissions: CRUD per model plus `mark_contacted_lead`, `qualify_lead`,
`disqualify_lead`, `reopen_lead`, `convert_lead`, `create_defaults_stage`,
`move_opportunity`, `pipeline_opportunity`, `complete_activity`. Profiles
(`crm/profiles.py`, additive): **Sales Manager** (everything), **Sales
Representative** (leads, opportunities, activities, no deletes or stage
configuration), **Customer Service Representative** (leads and activities),
**Auditor** (read). Root gets the action permissions in `crm/signals.py`.

## Frontend (`front/src/pages/crm`)

- **Pipeline** (`view_pipeline`): one column per open stage with its totals,
  opportunity cards, a menu to move a card (a lost stage asks for the reason),
  "only mine", and **Create default stages** when there are none.
- **Leads**: schema-driven list; the actions that need input (**Convert**,
  **Disqualify**) open dialogs, the others run directly.
- **Opportunity** page: stage selector, amount/customer/date/owner, activities
  with add and **Mark as done**.
- Opportunities, activities, stages: `s-auto-crud`.

## Tests

`crm/tests/test_crm.py`: default stages, lead transitions and protected
status, conversion (once, with an own/foreign customer), move won/lost/reopen,
stage and status not writable by CRUD, pipeline totals, activities, owner of
the Entity, isolation, foreign stage/lead, module inactive, crm without sales;
translations.

## Not implemented yet

Lead/activity reminders through notifications, e-mail capture, web forms that
create leads, quotes from an opportunity (would use sales), forecasting by
period.
