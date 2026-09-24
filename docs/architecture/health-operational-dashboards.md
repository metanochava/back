# Health operational dashboards (Reception, Nursing, Doctor, Laboratory)

Dashboards per work area of the `saude` module, built on the generic
declarative dashboard engine of `django_resaas`
(`django_resaas/docs/architecture/dashboards.md`) and on the patient flow of
an appointment (`Agenda`). There is no dashboard API, store or page per
profile: the engine serves them, and the home page shows the ones the user is
allowed to see as tabs.

```
Authenticated user
  -> signed tenant context (Entity + Branch + active Group)
  -> effective permissions of the active Group
  -> dashboards allowed (dashboard permission) -> widgets allowed (widget permissions)
  -> data scoped to the current Entity/Branch, "mine" resolved from request.user
```

## Status

| Area | Status |
|---|---|
| Reception, Nursing, Doctor dashboards | Implemented and tested |
| Waiting time / appointment delay | Implemented and tested |
| Laboratory: exam-only flow, lab check-in, collection time, result validation, dashboard | Implemented and tested |
| Pharmacy, Administrator | Next phases |
| Cashier / billing | Blocked: no invoice, receipt or cash register exists, and `saude` does not generate charges. Needs a decision on where they live (`sales` or a finance module). |
| Patient self-service area | Not started: needs its own endpoints with per-object scope (`User -> Person -> Paciente`). |

## Profiles (reused, never duplicated)

The existing profiles in `saude/profiles.py` are reused. No `Doctor`, `Nurse`
or `Receptionist` group was created. A profile only gets **default
permissions**. Which dashboard a user sees depends on the **permissions** of
their active group, never on the group's name. A custom group with the same
permissions gets the same dashboard.

| Dashboard | Dashboard permission | Profiles that get it by default |
|---|---|---|
| Reception (`saude_reception`) | `view_dashboard_saude_reception` | Medical Receptionist, Medical Secretary, Patient Services Coordinator |
| Nursing (`saude_nursing`) | `view_dashboard_saude_nursing` | Registered Nurse, Nurse Manager, Triage Coordinator |
| My Patients (`saude_doctor`) | `view_dashboard_saude_doctor` | General Practitioner, Specialist Physician |
| Laboratory (`saude_laboratory`) | `view_dashboard_saude_laboratory` | Medical Laboratory Technician, Medical Laboratory Scientist |

The dashboard permissions are created by `saude/signals/permissions.py`
(`DASHBOARD_PERMISSIONS`) and granted to Root. They are then assigned to the
profiles above by the idempotent, additive profile seed (`group_creator`: it
never removes custom permissions, and reports codenames that don't exist
instead of creating them). General Practitioner and Specialist Physician also
received `view_dadovital`, `add_dadovital` (a doctor can record vital signs)
and `view_resultadoexamemedico`.

Laboratory: both laboratory profiles received `check_in_pedidoexamemedico`,
and the Scientist also received `view_itempedidoexamemedico`,
`change_itempedidoexamemedico` and **`validate_resultadoexamemedico`**. Only
the Scientist validates; the Technician records. Reception profiles
(Medical Receptionist, Medical Secretary, Patient Services Coordinator)
received `view_pedidoexamemedico`, `add_pedidoexamemedico`,
`add_itempedidoexamemedico`, `view_examemedico` and
`check_in_pedidoexamemedico`, to register exam-only patients.

Known seed report: the Medical Laboratory Scientist profile lists
`view/add_paramentroresultadoexamemedico`, but the model
`ParamentroResultadoExameMedico` (`saude/models/parametroexamemedico.py`) is
never imported, so it has no table and no permissions. The seed reports these
two codenames as missing on every `migrate`; they are not created.

> Profiles are global Groups. Changing their permissions changes them for
> every Entity that uses them, and is a platform-level operation (see
> django_resaas *Permissions -> Managing group permissions*).

## Widgets, permissions and endpoints

All data comes from
`GET /api/django_resaas/dashboard/<dashboard>/widget/<widget>/` (**PROTECTED**:
authentication, signed context, active `saude` module, dashboard permission,
then widget permission; a missing permission is `403` and the widget is not
even listed). Providers: `saude/dashboard_flow_providers.py`.

| Dashboard | Widget | Type | Permissions | Data |
|---|---|---|---|---|
| Reception | `appointments_today` | stat | `view_agenda` | today's appointments, cancelled excluded |
| | `checked_in_today` | stat | `view_agenda` | today's appointments with `checked_in_at` |
| | `waiting_now` | stat | `view_agenda` | today's appointments in `em_espera` |
| | `average_waiting` | stat | `view_agenda` | average check-in -> service start, today (minutes) |
| | `reception_queue` | table | `view_agenda` | today's appointments by scheduled time; actions: open patient (`view_paciente`), register patient (`add_paciente`) |
| Nursing | `waiting_now` | stat | `view_agenda` | as above |
| | `vitals_pending` | stat | `view_agenda` + `view_dadovital` | waiting, no vital signs since check-in |
| | `ready_for_doctor` | stat | `view_agenda` + `view_dadovital` | waiting, vital signs recorded |
| | `vitals_recorded_today` | stat | `view_dadovital` | `DadoVital` records dated today |
| | `nursing_queue` | table | `view_agenda` + `view_dadovital` | waiting patients, vital signs pending first; actions: open patient, record vital signs (`add_dadovital`) |
| My Patients | `my_appointments_today` | stat | `view_agenda` | the user's appointments today (`Agenda.medico.person.user`) |
| | `waiting_for_me` | stat | `view_agenda` | the user's appointments in `em_espera` |
| | `completed_today` | stat | `view_agenda` | the user's appointments `concluida` today |
| | `pending_exams` | stat | `view_pedidoexamemedico` | open exam items (`pendente`, `agendado`, `colhido`, `processamento`) from the user's consultations |
| | `my_queue` | table | `view_agenda` | the user's appointments today that are not closed |
| | `recent_results` | list | `view_resultadoexamemedico` | **validated** results (`validado=True`) of exams the user requested, last 7 days; unvalidated results are never listed |

| Laboratory | `requests_today` | stat | `view_pedidoexamemedico` | requests created today (both origins) |
| | `pending_collection` | stat | `view_itempedidoexamemedico` | items `pendente`/`agendado` |
| | `in_process` | stat | `view_itempedidoexamemedico` | items `colhido`/`processamento` |
| | `results_to_validate_count` | stat | `view_resultadoexamemedico` | results linked to an exam item, not validated, not in the trash |
| | `lab_queue` | table | `view_pedidoexamemedico` + `view_itempedidoexamemedico` | requests with open items, checked-in first (then urgent); patient, arrival, lab waiting, exams, origin, status; actions: open request, open patient |
| | `results_to_validate` | list | `view_resultadoexamemedico` + `validate_resultadoexamemedico` | oldest unvalidated results. Only users who can validate see it. |

Queue actions open existing screens: appointments are checked in from the
patient record (`view_paciente`, `AgendaConsultaDialog`). The engine's actions
navigate; they do not call APIs.

## Multi-tenancy and scope

- Every queryset goes through the provider's `scoped_queryset()`: current
  Entity and Branch from the signed context. Nothing from the client
  selects a tenant.
- "Mine" (Doctor) is always `request.user` through `Agenda.medico` /
  `Consulta.employee -> Person.user`, never a parameter. A doctor employed in
  several Branches sees the Branch of the current context.
- Tested: another Entity sees none of the data (counts `0`, empty queues).

## Patient flow and waiting time

`Agenda` has three timestamps, **set by the server** when `estado` moves into
the state, whatever changed it (PATCH from the patient screen or creation):

| State | Timestamp |
|---|---|
| `em_espera` (checked in) | `checked_in_at` |
| `em_atendimento` | `service_started_at` |
| `concluida` | `completed_at` |

They are set only once: a repeated transition never overwrites the first time.
They are `editable=False`, so read-only in the API and the schema, and a
client that sends them is ignored. A walk-in created directly as `em_espera`
is checked in at creation.

Metrics (`saude/services/appointment_flow.py`):

- **Waiting time** = `checked_in_at -> service_started_at`, or up to now while
  still `em_espera`. `None` without a check-in, or when the appointment closed
  without being served (cancelled or no-show).
- **Delay** = scheduled time (`data` + `hora_inicio`) -> `service_started_at`,
  `0` when the service started on time or early, `None` until it starts.

Example: scheduled 10:00, check-in 09:50, start 10:17 -> **waiting 27 min,
delay 17 min**.

Waiting bands shown in the queues: `Normal` (<= 15 min), `Attention`
(<= 30), `Long wait` (> 30). These are defaults, not clinical rules. Override
them per installation:

```python
# settings.py
SAUDE_WAITING_THRESHOLDS = {"attention_after": 10, "long_wait_after": 20}
```

Only one waiting time is measured today: reception -> consultation. Waiting
times of other services (laboratory, pharmacy, cashier) will come with those
phases, on their own records.

## Laboratory flow

Two entry flows, one request model (`PedidoExameMedico`):

| Flow | How | Stored |
|---|---|---|
| Doctor request | from a consultation (`consulta` in the payload, or, as before, a clinician's request is attached to their consultation of the day with the patient) | `origin="consultation"`, `consulta`, `paciente` |
| Exam only | `POST /api/saude/pedidoexamemedicos/` with `{"paciente": id, "origin": "direct"}` (also when the requester has no employment in the Branch) | `origin="direct"`, **no consultation**, `paciente` |

- `paciente` and `consulta` are looked up **inside the current Entity**. An id
  from another Entity is `404 patient_not_found` / `consultation_not_found`.
  A consultation of another patient is `400 consultation_patient_mismatch`.
  (Before this phase the patient was looked up without tenant scope, and a
  requester without employment got a 500.)
- `paciente` and `origin` are read-only after creation. Requests created before
  this phase have their patient only through the consultation. Read it with
  `pedido.patient`, and filter with `PedidoExameMedico.patient_filter(p)`
  (used by the patient timeline). No data migration is needed.
- **Laboratory check-in**:
  `POST /api/saude/pedidoexamemedicos/{id}/check_in/` (`@resaas_action`,
  **PROTECTED**, permission `check_in_pedidoexamemedico`, scoped object:
  another Entity's request is `404`). It sets `checked_in_at` once;
  repeating it keeps the first time.
- **Collection**: when an item moves to `colhido` the server sets
  `data_colheita` (unless the client recorded the real time).
- **Laboratory waiting time** = `checked_in_at -> first data_colheita` of the
  request (or up to now while nothing is collected).

Results (`ResultadoExameMedico`):

- Recording needs `add`/`change_resultadoexamemedico`. **Validating needs
  `validate_resultadoexamemedico`**, on both paths:
  `POST /api/saude/resultadoexamemedicos/{id}/validate/` (`@resaas_action`), or
  `validado: true` in a create/update payload (the existing result screen
  sends the checkbox). Without the permission: `403 permission_denied`.
- `validado_por` and `data_validacao` are always set by the server (read-only
  in the API).
- A **validated result is never silently overwritten**: an update that changes
  any value is `409 result_already_validated` (`error.details.fields`).
  Re-sending the same values, as a whole-form save does, is accepted.
  Validating twice is `409`. Correction and amendment of a validated result
  (the model already has `numero_revisao`) is future work.

## Vital signs

The existing `DadoVital` model is reused (`paciente`, `consulta`, `employee`
= recorded by, `data`/`hora`, `created_at`; history is kept, one record per
measurement). For a queue, an appointment's vital signs count as
**recorded** when the patient has a `DadoVital` created **after the
check-in** (or dated on the appointment day when there was no check-in).
Measurements from before the check-in don't count. Nurses and, with
`add_dadovital`, doctors record them.

## Frontend

`quasar_resaas/components/dashboard/HomeDashboards.vue` shows, as tabs, the
authorized dashboards whose `module` is the Entity's EntityType (`saude`).
The first tab by `order` is the default (Reception 1, Nursing 2, My Patients
3, Clinic 10). The engine renders everything else (`DashboardRenderer`, one
component per widget type, loading/empty/error per widget). Queues refresh
every 60 s (`refresh.interval`). All labels are canonical English, translated
with `tdc()` (`saude/lang/*.py`, four languages).

## Extending

**A new profile** (e.g. Radiology Technician): reuse or add the profile in
`saude/profiles.py` with real codenames, including the dashboard permission of
the area it works in. No code reads the profile name.

**A new widget**: write a provider in `saude/dashboard_flow_providers.py`
(always `scoped_queryset()`, "mine" from `request.user`); declare it in the
dashboard's widget list with `permissions` (real codenames), `cols` (every row
must add up to 12 at every breakpoint); add the English labels to the four
`saude/lang` files; add a test for the data, the permission and tenant
isolation.

**A new area dashboard**: add an entry to `DASHBOARDS` in `saude/dashboard.py`
with a unique `name` and its own `view_dashboard_saude_<area>` permission, add
the permission to `DASHBOARD_PERMISSIONS`, and grant it to the profiles.

## Troubleshooting

| Symptom | Check |
|---|---|
| A dashboard tab doesn't appear | The active group (not another group of the same user) has `view_dashboard_saude_<area>`; the `saude` module is active for the Entity; the Entity's EntityType is `saude`. |
| A widget is missing | The active group lacks one of the widget's `permissions` (table above). |
| Waiting time shows `-` | The appointment was never moved to "Waiting" (no check-in), or it closed without being served. |
| Profile didn't get a new permission | Run `migrate` (the seed runs in `post_migrate`); check the log for `group_creator: profile ... expects permissions that do not exist`. |

Tests: `saude/tests/test_operational_dashboards.py`, `saude/tests/test_laboratory_flow.py`.
