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
| Laboratory: exam parameters, reference ranges, structured results with snapshots, release, amendment, sample rejection, TAT, history and evolution | Implemented and tested (see *Structured laboratory results*) |
| Pharmacy, Administrator | Next phases |
| Cashier / billing | Blocked: no invoice, receipt or cash register exists, and `saude` does not generate charges. Needs a decision on where they live (`sales` or a finance module). |
| Patient portal (self-service area) | Implemented and tested (see *Patient portal*) |

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

The dead model `ParamentroResultadoExameMedico` (never imported, no table)
was replaced by `ExamParameter` / `ExamReferenceRange`. Its codenames were
replaced in the profiles by the real ones, and the seed no longer reports
missing codenames for the laboratory profiles.

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
| | `recent_results` | list | `view_resultadoexamemedico` | **released** results (`released=True`) of exams the user requested, last 7 days; recorded or only validated results are never listed |

| Laboratory | `requests_today` | stat | `view_pedidoexamemedico` | requests created today (both origins) |
| | `pending_collection` | stat | `view_itempedidoexamemedico` | items `pendente`/`agendado` |
| | `in_process` | stat | `view_itempedidoexamemedico` | items `colhido`/`processamento` |
| | `results_to_validate_count` | stat | `view_resultadoexamemedico` | results linked to an exam item, not validated, not in the trash |
| | `lab_queue` | table | `view_pedidoexamemedico` + `view_itempedidoexamemedico` | requests with open items, checked-in first (then urgent); patient, arrival, lab waiting, exams, origin, status; actions: open request, open patient |
| | `results_to_validate` | list | `view_resultadoexamemedico` + `validate_resultadoexamemedico` | oldest unvalidated results. Only users who can validate see it. |
| | `results_to_record` | stat | `view_itempedidoexamemedico` | items `colhido`/`processamento` without any result |
| | `results_to_release` | stat | `view_resultadoexamemedico` + `release_resultadoexamemedico` | validated, not released (latest revision) |
| | `average_tat` | stat | `view_resultadoexamemedico` | average collection -> release of results released today |
| | `recollection_required` | stat | `view_itempedidoexamemedico` | items in `recolha_necessaria` |
| | `attention` | list | `view_itempedidoexamemedico` + `view_resultadoexamemedico` | rejected samples; unreleased values flagged critical by a **configured** critical range |

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

## Structured laboratory results

Code: `saude/models/exam_parameter.py`, `saude/models/result_parameter_value.py`,
`saude/services/lab_result_service.py`, `saude/services/exam_request_service.py`.
Tests: `saude/tests/test_structured_lab_results.py`.

```
ExameMedico (existing catalogue, per Entity/Branch)
  -> ExamParameter (code, type, unit, order, required, active, choices, patient_visible)
       -> ExamReferenceRange (sex?, age band?, low/high, critical_low/high?, label)
ItemPedidoExameMedico (one exam of a request)
  -> ResultadoExameMedico (existing header: report, PDF/attachment, revision, validation, release)
       -> ResultParameterValue (one per parameter: typed value + snapshot + flag)
```

### Exam definition

| Field | Meaning |
|---|---|
| `code` | stable technical key, unique per exam; history and evolution follow it |
| `name`, `unit`, `order` | as shown on the form and the report |
| `data_type` | `decimal`, `integer`, `text`, `boolean` (yes/no), `choice` (positive/negative, blood group, ...) |
| `decimal_places` | `decimal` only: the most decimal places a value may have |
| `choices` | `choice` only: the allowed values, e.g. `["Positive", "Negative"]` |
| `required`, `active` | an inactive parameter disappears from new forms; old values keep their snapshot |
| `patient_visible` | shown to the patient once released (patient area: next phase) |

Numeric parameters (`decimal`, `integer`) are the ones that can be charted.

**Reference ranges** (`ExamReferenceRange`, numeric parameters only) are laboratory
configuration. **No clinical value is seeded or defaulted anywhere.** For each
value the most specific active range that matches the patient's sex
(`Person.gender`) and age in days (`Person.date_of_birth`) applies: a range with
a sex beats one without, and a range with an age band beats one without. With no
matching range, the value has **no flag**. Critical limits are optional and only
flag what the laboratory configured.

Creating an exam: `ExameMedico` (existing screens) -> add its parameters
(`/api/saude/examparameters/`, `add_examparameter`) -> add reference ranges where
validated (`/api/saude/examreferenceranges/`, `add_examreferencerange`) -> the
result form of every item of that exam is built from them.

### Recording (dynamic form)

- `GET /api/saude/itempedidoexamemedicos/{id}/result_form/` (`view_itempedidoexamemedico`):
  the patient, the collection time and the exam's active parameters in order,
  each with its applicable reference and current value.
- `POST .../{id}/record_result/` (`record_result_itempedidoexamemedico`),
  body `{"values": {"hb": "14.2", "malaria": "Negative"}, "observacao"?, "laudo"?}`.
  The server validates everything. Unknown or other-exam parameters, missing
  required ones, non-numbers, fractions in an integer, too many decimals and values
  outside the choices are rejected with `400 invalid_result_values`, one message
  per field in `error.details`. Nothing is stored unless all values are valid.
- The first recording creates the result header (revision 1) with the values.
  Recording again **replaces the draft** until it is validated. After validation
  the answer is `409 result_already_validated`.
- **Snapshot**: every value stores the parameter code, name, type, unit, the
  reference low/high/label used and the flag. Renaming a parameter or changing a
  range later never rewrites old results (tested).
- Values are relational and typed (`value_numeric` Decimal, `value_text`,
  `value_boolean`), not JSON, so history and charts query them directly.

### Validation, release, amendment

| Step | Endpoint | Permission | Rule |
|---|---|---|---|
| Record | `record_result` | `record_result_itempedidoexamemedico` | draft, editable |
| Validate | `resultadoexamemedicos/{id}/validate/` (or the checkbox on the result screen) | `validate_resultadoexamemedico` | then immutable |
| Release | `resultadoexamemedicos/{id}/release/` | `release_resultadoexamemedico` | only after validation; `released`, `released_by`, `released_at` set by the server and read-only in the API |
| Amend | `resultadoexamemedicos/{id}/amend/` `{"reason"}` | `amend_resultadoexamemedico` | only the latest validated revision; creates revision N+1 (copy of the values, unvalidated). The validated one stays unchanged and is superseded. |

`numero_revisao` of a structured result is set by the server. History and
evolution use only the **latest revision of each exam item**. A superseded
revision is the record of the correction, not a second measurement. Recording,
validation, release, amendment, collection and rejection are written to the audit
log (`LAB_RESULT_RECORDED`, `LAB_RESULT_VALIDATED`, `LAB_RESULT_RELEASED`,
`LAB_RESULT_AMENDED`, `LAB_SAMPLE_COLLECTED`, `LAB_SAMPLE_REJECTED`).

**Legacy results** (free-text `valor_resultado`, report, PDF) are untouched and
still shown. They are never converted into structured values, so they do not
appear in evolution charts.

### Collection and sample rejection

- `POST itempedidoexamemedicos/{id}/collect/` (`collect_itempedidoexamemedico`):
  from `pendente`, `agendado` or `recolha_necessaria` to `colhido`. It sets
  `data_colheita` and `collected_by`.
- `POST .../{id}/reject_sample/` `{"reason"}` (`reject_sample_itempedidoexamemedico`):
  from `colhido` or `processamento` to **`recolha_necessaria`**. It keeps
  `rejected_at` and `rejection_reason` (the last one on the item, every one in the
  audit log). A new `collect` starts again.
- There is no separate Sample model. Collection is per exam item; sharing one
  sample between several exams needs a domain decision first.

### Waiting time vs turnaround time

- **Laboratory waiting** = laboratory check-in -> first collection (e.g.
  10:02 -> 10:20 = 18 min).
- **TAT** = collection (`data_colheita`) -> release (`released_at`) (e.g.
  10:25 -> 13:40 = 3h 15m). Shown on the Laboratory dashboard as the average of
  results released today.

### History and evolution

- `GET /api/saude/pacientes/{id}/lab_parameters/`: the parameters the patient
  has validated values for, marked `graphable` when numeric.
- `GET /api/saude/pacientes/{id}/lab_evolution/?parameter=<code>&from=&to=`:
  `{"parameter": {code, name, unit, numeric}, "points": [{result, date, value, unit, reference, flag}], "comparison": {current, previous, change}}`.
  Only validated results, the latest revision of each item, ordered by result
  date, filtered in the database. Values only, with no interpretation.
- Both are **PROTECTED** by `lab_evolution_paciente`. The patient is the URL
  resource (`get_object()`, scoped to the current Entity/Branch), so another
  Entity's patient is `404`. Values are limited to that patient and to the
  current Entity.

### Frontend (`dev/front`)

- `pages/saude/components/ExamResultDialog.vue`: one generic form for every
  exam, built from `result_form`: numbers, text, choice (select), yes/no
  (toggle), the unit as a suffix, the reference as a hint, flags. It becomes
  read-only once validated, and shows server field errors on each field. An exam
  without parameters records only the observation and the report. Opened from
  the results dialog (`AddResultadoModal`, "Record result" per exam).
- `pages/saude/components/LabEvolutionDialog.vue`: pick a parameter and a
  period. It shows the comparison (previous, current, change), a line chart
  (the engine's `LineChartWidget`; only numeric parameters with 2 or more points,
  never built from text) and the table of points. Opened from the patient record
  ("Lab evolution" button, shown with `lab_evolution_paciente`).

### Laboratory profiles (defaults)

| Permission | Technician | Scientist |
|---|:-:|:-:|
| `collect_itempedidoexamemedico`, `reject_sample_itempedidoexamemedico`, `record_result_itempedidoexamemedico`, `view_examparameter` | yes | yes |
| `validate_resultadoexamemedico`, `release_resultadoexamemedico`, `amend_resultadoexamemedico` | - | yes |
| `add/change_examparameter`, `view/add/change_examreferencerange`, `lab_evolution_paciente` | - | yes |

Doctors (General Practitioner, Specialist Physician) received `lab_evolution_paciente`.

### Known limitations

- Patient area (released results and trends for the patient) is the next phase.
  `released` and `patient_visible` are already in place for it.
- No unit conversion, and no critical-result notification workflow beyond the
  dashboard's *Attention Required* list.
- The legacy results dialog's own "Save result" button calls a function that
  doesn't exist in `AddResultadoModal.vue`. This predates the change and is
  reported separately; the new "Record result" button next to it uses the
  structured flow.

## Patient portal

Code: `saude/services/patient_portal_service.py`, `saude/views/patient_portal.py`,
`dev/front/src/pages/saude/myhealth/`. Tests: `saude/tests/test_patient_portal.py`.

### Access (granted by staff, per Entity)

- `POST /api/saude/pacientes/{id}/grant_portal_access/` and
  `.../revoke_portal_access/`. **PROTECTED** by `grant_portal_access_paciente`
  (default: Medical Receptionist, Medical Secretary, Patient Services
  Coordinator). The patient is `get_object()`, so another Entity's patient is
  `404`.
- Granting makes the person's User (every `Person` already has one) a member of
  the Entity (`EntityUser`, **no Branch, no profile**) and sets
  `Paciente.portal_access`, with who and when (server-controlled, read-only).
  When the person has no permanent password yet, a new **temporary password**
  is issued (the existing `temporary_password_service`) and returned **once**,
  to hand to the patient. It must be changed at first login. A password the
  person chose is never overwritten.
- Revoking clears the flag and soft-deletes the membership, unless the person
  also works in that Entity. The signed context is re-validated on every
  request, so access ends immediately.
- Both are audited (`PATIENT_PORTAL_GRANTED`, `PATIENT_PORTAL_REVOKED`).
- There is no self-registration.

### Self-service API

`GET /api/saude/me/<section>/`, read only, **PROTECTED**:
authentication -> signed context (Entity only) re-validated for the user ->
`saude` active -> **the user's own `Paciente` of that Entity with
`portal_access`** -> that patient's data. **No endpoint takes a patient id**.
Anything in the query string or body is ignored, so patient A cannot even ask
for patient B's data (tested with `?paciente=<B>`).

| Section | Content |
|---|---|
| `status` | `{portal, patient}`, always `200` (the welcome page uses it) |
| `summary` | name, next appointment, pending exams, results released in the last 30 days, prescriptions count |
| `appointments` | upcoming and previous (date, time, doctor, status) |
| `exams` | own exam items with a patient-facing status; "Result available" once released |
| `results` | **released** results only (latest revision), with values of `patient_visible` parameters (value, unit, reference, flag) and the report |
| `trends` | numeric, patient-visible parameters with released values; `?parameter=<code>&from=&to=` gives the series (released only) |
| `prescriptions` | own prescriptions with medicines, dosage, quantity, instructions |
| `vitals` | latest and last 10 vital-sign records |

Scope is the Entity of the context, across its Branches. A person who is a
patient in two Entities sees, in each, only that Entity's data, and only where
access was granted. Validation metadata, internal notes and non-visible
parameters are not returned. Unreleased or superseded results never appear.

### Frontend

- After login, a user with no Branch lands on the welcome page. It calls
  `me/status/` and shows **My Health** when the portal is available.
- `/my_health` (`MyHealthPage.vue`, no `requiredRole`: the backend enforces
  access) shows a header with the next appointment, KPIs, and tabs for
  appointments, exams, results, trends (the engine's `LineChartWidget`, from 2
  points), prescriptions and vital signs.
- Patient record (`PacienteVPage`, personal tab): the portal status badge and
  grant/revoke buttons (shown with `grant_portal_access_paciente`). The
  temporary password is displayed once, in a dialog (values HTML-escaped).

Billing is not in the portal: invoices, receipts and payments do not exist yet
(see *Status*).

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

Tests: `saude/tests/test_operational_dashboards.py`, `saude/tests/test_laboratory_flow.py`,
`saude/tests/test_structured_lab_results.py`, `saude/tests/test_patient_portal.py`.
