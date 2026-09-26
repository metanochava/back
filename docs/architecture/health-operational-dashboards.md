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

## Profiles (the 9 official saude profiles)

`saude/profiles.py` defines nine access profiles, seeded by `group_creator()`
(idempotent, additive: custom permissions are preserved, and missing codenames are
reported, never created):

| Profile | Purpose | Operational dashboard |
|---|---|---|
| Doctor | consultations, diagnoses, prescriptions, exam requests, vital signs, own lab results and evolution | My Patients (`view_dashboard_saude_doctor`) |
| Nurse | vital signs, clinical observations, current medication, vaccination | Nursing (`view_dashboard_saude_nursing`) |
| Medical Receptionist | patient registration, appointments, exam-only requests, lab check-in, **patient portal grant** | Reception (`view_dashboard_saude_reception`) |
| Medical Laboratory Technician | collect / reject samples, record results | Laboratory (`view_dashboard_saude_laboratory`) |
| Medical Laboratory Scientist | Technician + validate, release, amend results, configure exam parameters and reference ranges | Laboratory |
| Pharmacist | prescriptions and medicines (the `farmacia` module adds dispensing to the same Group) | - |
| Cashier | the patient only (`view_paciente`); billing permissions come from the `sales` module, which seeds the same Group | - |
| Healthcare Administrator | read-only supervision of clinical activity | Clinic (`view_dashboard_saude_clinica`) |
| Patient | the patient portal only (see *Patient portal*) | My Health (`saude_patient`, `view_patient_portal`) |

Which dashboard a user sees depends on the **permissions** of their active
profile, never on its name. A custom group with the same permissions gets the
same screens.

`Pharmacist` and `Cashier` are also profiles of `farmacia` and `sales`. Group names
are global, so each module adds its own permissions to the **same** Group: one
pharmacist or cashier profile across modules.

**Renaming.** Existing groups are renamed in place (same `Group.id`, users and
permissions kept) by `SAUDE_RENAME_FROM`, which accepts a list of old names:
`Doctor` <- `General Practitioner` / `Médico Geral`, `Nurse` <- `Registered Nurse` /
`Enfermeiro`, and the Portuguese names of the others. Groups of the previous
catalogue that are not in the nine (e.g. Specialist Physician, Nurse Manager,
Medical Secretary) are **not deleted**. They keep working with the permissions they
have, but are no longer seeded.

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
| | `reception_queue` | table | `view_agenda` | today's appointments by scheduled time; row actions: check in (`check_in_agenda`, scheduled/confirmed rows), check out (`check_out_agenda`, waiting/in-progress rows), open patient (`view_paciente`); toolbar: register patient (`add_paciente`) |
| Nursing | `waiting_now` | stat | `view_agenda` | as above |
| | `vitals_pending` | stat | `view_agenda` + `view_dadovital` | waiting, no vital signs since check-in |
| | `ready_for_doctor` | stat | `view_agenda` + `view_dadovital` | waiting, vital signs recorded |
| | `vitals_recorded_today` | stat | `view_dadovital` | `DadoVital` records dated today |
| | `nursing_queue` | table | `view_agenda` + `view_dadovital` | waiting patients, vital signs pending first; row actions: record vital signs (dialog, `add_dadovital`), open patient |
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

### Check-in and check-out (reception)

The reception moves an appointment with two explicit actions instead of
editing its state:

| Action | Permission | From | To | Rule |
|---|---|---|---|---|
| `POST /api/saude/agendas/{id}/check_in/` | `check_in_agenda` | `marcada`, `confirmada` | `em_espera` (`checked_in_at`) | only on the appointment day (`409 not_appointment_day`) |
| `POST /api/saude/agendas/{id}/check_out/` | `check_out_agenda` | `em_espera`, `em_atendimento` | `concluida` (`completed_at`) | a waiting patient may leave too (the doctor may not have pressed "start") |

- Any other state gives `409 invalid_appointment_state` and nothing changes.
  The row is locked (`select_for_update`), so a double click moves it once.
- `get_object()` keeps the appointment inside the current Entity/Branch
  (another tenant's id → 404). The `Medical Receptionist` profile gets both
  permissions (`saude/profiles.py`, additive seed).
- Where: **Reception Queue** row buttons, each shown only on the rows whose
  `estado` allows it (dashboard action `type: "request"` + `when`), and the
  **Upcoming Appointments** list of the patient record (`PacienteVPage`,
  check-in only for today's appointments, check-out after a confirmation).
- A free `PATCH` of `estado` (edit appointment dialog) still works as before.
  It is not limited to these transitions yet.

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

### Frontend (dev/front)

The actions come from the schema (`@resaas_action`) and each one only appears
when the user has its permission (UX only). The backend still checks the permission
(`403`) and the state (`409`).

| Where | Action | How |
|---|---|---|
| Exam request list (`PedidoexamemedicoLPage`, AutoCrud) | Check in | `autorequest=True`: AutoCrud posts and reloads |
| Exam item list (`ItemPedidoexamemedicoLPage`, AutoCrud) | Collect | `autorequest=True` |
| | Reject sample | `sDialog` prompt for the reason -> `reject_sample` -> list reload |
| | Record result | opens `ExamResultDialog` (also opened from `AddResultadoModal`) |
| `ExamResultDialog` footer | Validate / Release / Amend | shown by the state in `result_form.result` (`validated`, `released`) and `User.can('<action>_resultadoexamemedico')`. Amend asks for the reason and then shows the new revision |

`result_form` is a data endpoint for the dialog. It is declared `visible=False`, so
it is not a menu entry.

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

The Doctor profile has `lab_evolution_paciente`.

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
  (default: Medical Receptionist; never the Patient profile). The patient is
  `get_object()`, so another Entity's patient is `404`.
- Granting gives the person's User (every `Person` already has one) the
  **Patient profile at the patient's Branch**: `EntityUser` + `BranchUser` +
  `BranchUserGroup(user, Paciente.branch, Patient)`, plus the Entity's
  `EntityGroup` link to the profile. All of it is idempotent: repeating the grant,
  or granting again after a revoke, restores the same rows and creates no duplicate.
  Nothing else the user has is changed. It also sets `Paciente.portal_access`,
  with who and when (server-controlled, read-only). The Patient Group is the one
  seeded by `group_creator()`. If it is missing, the grant fails with
  `409 patient_profile_missing` instead of creating a partial configuration.
  When the person has no permanent password yet, a new **temporary password**
  is issued (the existing `temporary_password_service`) and returned **once**,
  to hand to the patient. It must be changed at first login. A password the
  person chose is never overwritten.
- Revoking clears the flag and soft-deletes **only the Patient profile** of that
  Entity. The Patient profile never counts as a working relationship. A
  `BranchUser` is removed only where no other profile is left on that Branch,
  and the `EntityUser` only when no other profile is left in the Entity and the
  person is not its admin. **A patient who is also staff** (e.g. Nurse +
  Patient) keeps the professional profile, membership and login. The signed
  context is re-validated on every request, so access ends immediately.
- Both are audited (`PATIENT_PORTAL_GRANTED`, `PATIENT_PORTAL_REVOKED`).
- There is no self-registration.

### Self-service API

`GET /api/saude/me/<section>/`, read only, **PROTECTED**, two barriers:

```
authentication -> signed context re-validated for the user -> saude active
  -> PERMISSION of the section in the active profile      (ActionPermissionMixin)
  -> OWNERSHIP: the user's own Paciente of that Entity with portal_access
  -> that patient's data only
```

| Section | Permission (Patient profile) |
|---|---|
| `status` | none - always `200 {portal, patient}`; `portal` is false without `view_patient_portal` |
| `summary` | `view_patient_portal` |
| `appointments` / `exams` / `results` / `trends` / `prescriptions` / `vitals` | `view_own_appointments` / `view_own_exams` / `view_own_results` / `view_own_trends` / `view_own_prescriptions` / `view_own_vitals` |

These are portal capabilities (created in `saude/signals/permissions.py`, on the
`Paciente` ContentType), not clinical model permissions. `view_own_results` lets
the profile **use** the results section; it never means "any
`ResultadoExameMedico`", because every query starts from the caller's own
`Paciente`. **No endpoint takes a patient id**. Anything in the query string or
body is ignored, so patient A cannot even ask for patient B's data (tested with
`?paciente=`, `?patient_id=`, `?id=`).

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

### Patient dashboard (`saude_patient`)

The Patient profile's home, declared in `saude/dashboard.py` (`DASHBOARDS`) and
served by the dashboard engine like the others. The dashboard permission is
`view_patient_portal`; each widget needs its portal capability, so a profile
missing one doesn't get that widget (not listed, `403` if asked). No operational
dashboard permission is involved.

| Widget | Type | Permission | Data |
|---|---|---|---|
| `next_appointment` | stat | `view_own_appointments` | next appointment (date, time; doctor as caption) |
| `pending_exams` | stat | `view_own_exams` | own exams in an open state **without** a released result |
| `new_results` | stat | `view_own_results` | results released in the last 30 days |
| `prescriptions` | stat | `view_own_prescriptions` | own prescriptions |
| `upcoming_appointments` | table | `view_own_appointments` | next 10 appointments |
| `recent_results` | list | `view_own_results` | last 5 **released** results, first values |
| `latest_vitals` | list | `view_own_vitals` | latest vital-sign record |

**Ownership, not tenant scope.** The providers
(`saude/dashboard_patient_providers.py`) resolve the caller's own `Paciente`
(`patient_portal_service.resolve_self`) and reuse the portal's data functions. The
engine's `scoped_queryset` (Entity + Branch) is not used, because it would still
cover every patient of the Branch. Without portal access the widgets are empty,
including for a staff profile given the same permissions (tested). The same rules
as the portal apply: released results only, patient-visible parameters.

`MyHealthPage` shows it at the top (`<s-dashboard-renderer name="saude_patient" />`),
followed by the detail tabs. On the home page it is the first tab (`order: 0`)
for a profile that has it.

### Frontend

- **Login**: the normal RESAAS login (username/password, temporary password
  change, 2FA policies) -> Entity -> the patient's Branch -> the Patient profile.
  There is no separate patient authentication.
- The welcome page calls `me/status/`. When the portal is available **and** the
  active profile has `view_patient_portal`, it goes straight to `/my_health`.
  This is decided by capability, never by the profile's name, so a Nurse +
  Patient acting as Nurse is not redirected.
- The saude menu shows **My Health** only with `view_patient_portal`. Every
  other saude item needs a clinical permission the Patient profile doesn't have,
  so the patient sees only the portal. The backend enforces the same.
- `/my_health` (`MyHealthPage.vue`, `requiredRole: view_patient_portal`) shows the
  Patient dashboard and **only the tabs whose `view_own_*` permission the
  profile has**: appointments, exams, results, trends (the
  engine's `LineChartWidget`, from 2 points), prescriptions, vital signs.
- Patient record (`PacienteVPage`, personal tab): the portal status badge and
  grant/revoke buttons (shown with `grant_portal_access_paciente`). The
  temporary password is displayed once, in a dialog (values HTML-escaped).

Billing is not in the portal: invoices, receipts and payments do not exist yet
(see *Status*).

## Vital signs

The existing `DadoVital` model is reused (`paciente`, `consulta`, `employee`
= recorded by, `data`/`hora`, `created_at`; history is kept, one record per
measurement). Migration `0007` adds three nullable fields: `agenda` (the
visit), `temperatura_local` (axillary/oral/tympanic/rectal) and
`glicemia_momento` (fasting/postprandial/random). Existing rows are
unchanged.

For a queue, an appointment's vital signs count as **recorded** when a
`DadoVital` is linked to it (`agenda`). Older records without that link fall
back to the previous rule: a record of the patient created **after the
check-in**, or dated on the appointment day when there was no check-in.
Nurses and, with `add_dadovital`, doctors record them.

### Recording from a dashboard queue

Nursing Queue and My Queue (doctor) have a **Record vital signs** row action
(`type: "dialog"`, `dialog: "saude.record_vital_signs"`, `add_dadovital`). It
opens `VitalSignsDialog.vue` (dev/front) for the appointment of the row:

| Step | API | Rule |
|---|---|---|
| Context | `GET /api/saude/dadovitals/intake/?agenda=<id>` (`add_dadovital`) | patient (name, age, gender, NID, photo), appointment, doctor, the professional signed in, the previous record, the limits. The appointment must be in the current Entity + Branch (`404 appointment_not_found`). A user without an Employee in this Branch gets `400 professional_required`. |
| Save | `POST /api/saude/dadovitals/` (`add_dadovital`) | only the vital signs, `agenda` and `tipo` are sent. The server sets `employee` = the caller's Employee (a client value is ignored: `employee` is read only), `paciente` and `consulta` from the appointment (a different patient → `400 patient_mismatch`), entity/branch from the context. |
| Limits | both | physiologically possible values (e.g. temperature 30–45 °C, SpO₂ 50–100 %, diastolic < systolic). Outside them → `400` with one message per field (`error.details`). These catch typing errors; they are not clinical ranges. |

The dialog shows the context read only and one tile per measurement (unit,
min/max, previous value and difference). Each tile has a colour: normal,
attention, warning or critical, using adult reference values. A side panel
calculates live: BMI and class, ideal weight (BMI 22), mean arterial
pressure, pulse pressure, shock index (HR/SBP) and waist-to-height ratio. It
also lists the alerts. These are decision support: the dialog says so, and
nothing is stored besides the measurements. After saving, the dashboard's
widgets reload, so the counters and the queue update.

### Recording from the patient header

`PacienteHeaderPage.vue` has a **Record vital signs** icon (`monitor_heart`).
It is shown only with `add_dadovital`; the backend checks the same permission.
It opens the same `VitalSignsDialog.vue` with `patient-id` instead of a
dashboard row:

- `GET /api/saude/dadovitals/intake/?paciente=<id>` (`add_dadovital`) returns
  the same context. The server uses the patient's latest open appointment of
  today in this Branch (not `cancelada` / `faltou`) when there is one; the
  dialog then saves with `agenda`, exactly like the queue. Without one,
  `agenda` and `doctor` are `null`, the dialog shows "No appointment today"
  and saves with `paciente`. That is the existing record without appointment
  (`prepare_create`: the patient must be of this Entity).
- A patient of another Entity → `404 patient_not_found`. `?agenda=` wins when
  both are sent.


## Consultation form (`add_consulta` / `change_consulta`)

A professional form (`ConsultaSEPage.vue`), not the generic CRUD form:

- **Top:** the patient header and **Latest vital signs**
  (`LatestVitalSigns.vue`). It shows the last `DadoVital` of the patient
  (`GET dadovitals/?paciente=&ordering=-created_at&page_size=1`), each value
  with the same adult reference bands as the recording dialog, BMI / MAP /
  pulse pressure / shock index, the alerts, when and by whom it was recorded,
  and a badge when it is older than 24 h.
- **Form:** chief complaint and history (required), diagnosis, plan, bound to
  the `Consulta` store form, each an `s-editor` (rich text, like the other
  clinical documents). They are stored as HTML and the PDF renders them as
  HTML (`consultamedicabody.html`). The required check reads the text without
  the HTML, because `q-form` does not validate `s-editor`. The patient comes from the context (the patient
  open in the header, or the consultation being edited); without one the
  page asks to open a patient first.
- **Professional:** the one signed in, shown from
  `GET /api/saude/consultas/intake/?paciente=<id>` (`add_consulta`: the
  professional, the patient scoped to the tenant, and today's appointment of
  this patient with this doctor). `POST consultas/` sets it again on the
  server: `employee` is read only and a client value is ignored. A user
  without an Employee in the Branch gets `400 professional_required`. A
  patient of another Entity gets 404.
- Vital-sign bands and calculations live in one place,
  `pages/saude/components/vitalSigns.js`, used by the recording dialog and by
  this card.
- `PacienteHeaderPage` accepts `patient-id`, for pages whose route `:id` is
  not the patient (`change_consulta/:id` is the consultation).

### Consultation PDF

`GET /api/saude/consultas/{id}/pdf/` (`pdf_consulta`, which the Doctor profile
has, like the PDF of every document it can view) follows the form, in the same
order:

1. the patient header (name, NID, occupation, contact);
2. the professional, the date and the appointment time;
3. the vital signs of the visit: the record linked to the consultation, or the
   patient's last one taken before it, with each value's status, the same
   calculations and the alerts;
4. chief complaint and history (full width), then diagnosis and plan side by
   side.

Every text is translated in the requester's language
(`consultation_service.pdf_context`, `Translate.tdc`). The status bands and
calculations are the frontend's (`vitalSigns.js`) mirrored in
`vital_signs_service` (`RULES`, `calculations`). Change both together:
`test_consultation_pdf.py` pins the shared cases.

## Prescriptions and the other documents of a visit

The same rule applies to prescriptions (`receitamedicas`), medical
certificates (`atestadomedicos`), referrals (`guiatransferencias`) and medical
reports (`relatoriomedicos`): `consultation_service.resolve_for_document`.
All four used to `get_or_create` a consultation. Exam requests from a
clinician keep attaching to the consultation of the day, now through
`todays_consultation()`, and create one only when there is none. Two
consultations on the same day no longer break them either.

- **A prescription belongs to a consultation of today** of the patient
  (`consultation_service.resolve_for_document`). The server picks the
  consultation of today's appointment with this doctor first, then this
  doctor's latest consultation of the patient today. With none:
  `409 consultation_required` ("start the consultation first"). No
  consultation is ever created by `POST receitamedicas/` (it used to
  `get_or_create` one and failed with `MultipleObjectsReturned` when there
  were two). A `consulta` sent by the client must be of this patient, Branch
  and day (`400 invalid_consultation`). A patient of another Entity gets 404.
- **Consultation ↔ appointment:** `POST consultas/` links the new
  consultation to today's appointment of the patient with this doctor (the
  first not closed and still without one: `Agenda.consulta`).
- **Prefill:** choosing a medication calls
  `GET /api/saude/medicamentos/{id}/prescription_defaults/` (`view_medicamento`).
  It returns the dosage and quantity of the last prescription of that
  medication in the Entity (this doctor's first, then anyone's), else the
  catalogue dosage (`source`: `last_prescription` | `catalogue` | null). The
  page never replaces what the doctor typed, and says where the values came
  from. Without history the catalogue's own `dosagem` and `quantidade` are
  used. `Medicamento.quantidade` (text, nullable) is new: migration
  `0008_medicamento_quantidade`, and existing rows keep `null`. The "New
  medication" dialog of the prescription page asks for it.

### Editing a clinical document: author only, within 24 h

Consultations, prescriptions and their items, certificates, referrals,
medical reports and exam requests can be changed only by **the user who
created them** (`created_by`), and only **within 24 hours of `created_at`**
(`saude/services/document_edit_policy.py`, `DocumentEditWindowMixin` on those
views' `perform_update`: `PATCH` and `PUT`).

| Case | Answer |
|---|---|
| Author, within the window | normal update |
| Another user, even with `change_<model>` | `403 not_document_author` |
| After the window, even the author | `409 edit_window_expired` |

- The rule comes on top of the permission (`change_<model>`) and of the tenant
  scope (`get_object()` on the scoped queryset). It does not replace them.
- The window is `settings.SAUDE_DOCUMENT_EDIT_WINDOW_HOURS` (default 24).
- Exam request **items** (`itempedidoexamemedicos`) are not restricted: the
  laboratory updates them (collection, results) through its own actions and
  permissions.
- Frontend (UX only): `pages/saude/components/documentEditPolicy.js`
  (`canEditDocument`). The history list hides **Edit** / **Reprint** for
  documents that can no longer be edited. `ConsultaSEPage` shows a read-only
  banner and disables saving.
- Tests: `saude/tests/test_document_edit_policy.py`.

### Patient card PDF

`GET /api/saude/pacientes/{id}/pdf/` (`pdf_paciente`) renders a CR80 card
(85.6 × 54 mm, front and back, `saude/paciente.html`) from
`patient_card_service.pdf_context`:

- **Front:** logo, Entity and Branch, the photo (`Person.photo`, else the
  user's profile picture), the name, date of birth and age, blood type and
  gender, the phone, and the NID as the card number. The QR code holds the
  patient id.
- **Back:** allergies (`alergias_correntes` + `alergias_medicamentosas`,
  highlighted in red when present), chronic diseases (`doencas_correntes`),
  usual medication (`medicacoes_correntes`), the emergency contact
  (`Person.contacts` with `is_emergency`, the primary one first), the
  clinical alert when there is one, the health unit, and a barcode of the
  NID.
- Each list shows at most 3 entries, then `+N`. Labels are translated with
  the requester's language (`Translate.tdc`).

## Demo data (`seed_saude_demo`)

Creates demo patients and one doctor's appointments around today, so the
dashboards and the reception / nursing / doctor flows can be tried on a fresh
database. Run it after the base bootstrap (`create_entity` or `resaas_setup`),
which creates the Entity, the Branch and the users.

```bash
python manage.py seed_saude_demo --entity Amal --doctor-user cassia            # 2 days before .. 3 after
python manage.py seed_saude_demo --entity Amal --branch Sede --doctor-user cassia \
    --days-before 7 --days-after 7 --patients 20 --min-per-day 6 --max-per-day 10
python manage.py seed_saude_demo --entity Amal --doctor-user cassia --reset    # rebuild the demo days
python manage.py seed_saude_demo --entity Amal --doctor-user cassia --dry-run  # show, write nothing
```

| What | How |
|---|---|
| Patients | at least `--patients` (default 12) demo patients in the Branch, NID `DEMO-<branch>-NNN`, reused on every run |
| Doctor | the Person of `--doctor-user` (username or email). An Employee record in the Branch is created when missing. No user or password is ever created. |
| Appointments | 30-min slots 08:00–16:30, `--min/--max-per-day` (9–12), never over the doctor's existing appointments, one per patient per day, tagged `[demo-seed]` in `observacao` |
| States | past days: completed / no-show / cancelled; today: 3 completed, 2 waiting, 1 in progress, the rest scheduled/confirmed (to try check-in); future days: scheduled/confirmed |
| Flow times | `checked_in_at` / `service_started_at` / `completed_at` coherent with the state, so waiting and delay metrics have values |

Rules:
- `--entity` is required. `--branch` is required when the Entity has more
  than one: nothing is ever picked as "the first".
- Running it again skips the days that already have demo appointments.
  `--reset` deletes only this doctor's demo appointments in the range and
  creates them again. Real appointments are never touched. The appointments
  created by hand before the command existed (`[seed] test data for Dr.
  Cassia`) are treated as demo.
- `--seed N` makes the data reproducible. `--dry-run` rolls everything back.
- With `DEBUG` off it refuses to run without `--allow-production`, because
  demo patients are not real data.

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
