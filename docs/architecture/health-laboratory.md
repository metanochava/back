# Health laboratory

> See also: [Health operational dashboards](health-operational-dashboards.md)
> (profiles, the Laboratory dashboard's place among the others, patient portal,
> vital signs) and [Patient longitudinal health](patient-longitudinal-health-pharmacy.md).
> Core mechanisms reused here are documented in django_resaas: permissions and
> `group_creator` (`docs/security/permissions.md`), `AuditLog` / `audit_service`
> (`docs/architecture/overview.md`), dashboards (`docs/architecture/dashboards.md`).

The `saude` laboratory: exam requests (doctor request or exam only), the
laboratory queue, sample collection, structured results built from a
configurable exam definition, separate record / validate / release steps,
amendment, history, charts, the doctor's and the patient's views, and the
Laboratory dashboard. Code: `saude/models/`, `saude/services/exam_request_service.py`,
`saude/services/lab_result_service.py`, `saude/services/patient_portal_service.py`,
`saude/views/`, `dev/front/src/pages/saude/`.

## Status

Implemented in 19 controlled phases (audit -> domain model -> gap analysis ->
database -> permissions -> exam configuration -> queue -> collection ->
structured results -> validation/release -> history -> charts -> doctor ->
patient -> dashboard -> security audit -> performance -> tests -> documentation).
Everything below is implemented and covered by tests unless marked
**Planned** / **Not implemented**.

## Architecture

```
Person (core) ── User (core)
   └── Paciente (Entity + Branch)
          │
Consulta (optional) ──┐
                      ▼
PedidoExameMedico   paciente, origin {consultation | direct}, checked_in_at, urgente
   └── ItemPedidoExameMedico   exame, prioridade, estado_exame (read-only in the API),
          │                    data_colheita, collected_by, rejected_at, rejection_reason
          ▼
ResultadoExameMedico   one row per REVISION (numero_revisao); validado/_por/_at,
   │                   released/_by/_at, valor_resultado, laudo, file
   └── ResultParameterValue   SNAPSHOT (code, name, type, unit, reference) + value + flag

TipoExameMedico -> ClasseExameMedico -> ExameMedico
                                          └── ExamParameter (type, unit, order, required, active,
                                                  choices, patient_visible, graphable)
                                                └── ExamReferenceRange (sex?, age band?, low/high,
                                                        critical low/high?)
AuditLog (django_resaas)   every laboratory step, with `details` (reason, from/to, revision)
```

| Model | Owns | Tenant | Patient |
|---|---|---|---|
| `ExameMedico`, `ExamParameter`, `ExamReferenceRange` | exam definition (configuration, never clinical defaults) | Entity (+ Branch fields of `BaseModel`) | - |
| `PedidoExameMedico` | the request; laboratory arrival | Entity + Branch | `paciente` (older requests: through `consulta`) |
| `ItemPedidoExameMedico` | one exam of the request; its state and collection | Entity + Branch | the request's |
| `ResultadoExameMedico` | a result revision (also the results explorer's folders/files) | Entity + Branch | `paciente` = the item's request patient (enforced) |
| `ResultParameterValue` | one structured value with its snapshot | Entity + Branch | the result's |

There is **no Sample model** (deferred: collection is per exam item; see
*Collection and sample rejection*). No model was added by the laboratory work:
the phases extended existing ones (`graphable`, `value_date`, `AuditLog.details`).

## Workflow

Exam item (`estado_exame`; changed **only** by the actions, each with its
permission, transaction, row lock and audit entry):

```
pendente / agendado ──collect──► colhido ──start_processing──► processamento
      ▲                              │                               │
      └──── collect ◄── recolha_necessaria ◄──reject_sample──────────┘
                                     │
   result validated ─────────────────┴────────────────────────────► concluido
   amend (validated result) ─────────── concluido ──► processamento
   cancel (any state before concluido) ──► cancelado   (final: nothing is
                                                        collected, recorded or
                                                        validated afterwards)
```

Result: **record** (`record_result` structured / `record_report` free-form, same
row, editable while not validated) -> **validate** (needs content; completes the
item; immutable afterwards) -> **release** (only validated; the patient and the
requester's views show released results only) -> **amend** (new revision N+1;
N stays unchanged until N+1 is released).

## API reference

All endpoints are **PROTECTED** (`BaseAPIView`: authentication, signed tenant
context, active module, per-action permission; missing permission = `403`).
Detail endpoints use `get_object()` on the Entity + Branch scoped queryset:
another tenant's id is `404`. Base path `/api/saude/`.

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| POST | `pedidoexamemedicos/` | `add_pedidoexamemedico` | request (doctor request or `{"origin": "direct"}` exam only) |
| POST | `pedidoexamemedicos/{id}/check_in/` | `check_in_pedidoexamemedico` | laboratory arrival (once) |
| GET | `pedidoexamemedicos/{id}/items/` | `view_pedidoexamemedico` | the request's exams with their results |
| GET | `pedidoexamemedicos/{id}/resultados/` | `list_resultadoexamemedico` | the request's results |
| GET | `itempedidoexamemedicos/{id}/result_form/` | `view_itempedidoexamemedico` | dynamic form definition (parameters, references, current values) |
| POST | `itempedidoexamemedicos/{id}/record_result/` | `record_result_itempedidoexamemedico` | structured values `{"values": {code: value}}` |
| POST | `itempedidoexamemedicos/{id}/record_report/` | `record_result_itempedidoexamemedico` | free-form value / report / file (multipart) |
| POST | `itempedidoexamemedicos/{id}/collect/` | `collect_itempedidoexamemedico` | sample collected |
| POST | `itempedidoexamemedicos/{id}/reject_sample/` | `reject_sample_itempedidoexamemedico` | `{"reason"}` -> recollection required |
| POST | `itempedidoexamemedicos/{id}/start_processing/` | `start_processing_itempedidoexamemedico` | collected -> processing |
| POST | `itempedidoexamemedicos/{id}/cancel/` | `cancel_itempedidoexamemedico` | `{"reason"}` -> cancelled |
| GET | `itempedidoexamemedicos/{id}/trail/` | `view_itempedidoexamemedico` | the exam's audit trail |
| POST | `resultadoexamemedicos/{id}/validate/` | `validate_resultadoexamemedico` | validate (the only path) |
| POST | `resultadoexamemedicos/{id}/release/` | `release_resultadoexamemedico` | release |
| POST | `resultadoexamemedicos/{id}/amend/` | `amend_resultadoexamemedico` | `{"reason"}` -> new revision (`201`) |
| GET | `pacientes/{id}/lab_parameters/` | `lab_evolution_paciente` | parameters with validated values |
| GET | `pacientes/{id}/lab_evolution/` | `lab_evolution_paciente` | one parameter's series + comparison |
| GET | `pacientes/{id}/lab_history/` | `lab_evolution_paciente` | validated results with snapshots, filtered, paginated |
| GET | `pacientes/{id}/lab_summary/` | `lab_evolution_paciente` | consultation panel: open exams + recent released results |
| CRUD | `examparameters/`, `examreferenceranges/` | `list_/view_/add_/change_/delete_…` | exam configuration |
| GET | `me/exams/`, `me/results/`, `me/trends/` | `view_own_exams` / `view_own_results` / `view_own_trends` | patient portal (own data only) |

Successful action `POST`s answer `202` (`201` for amend), per the RESAAS status
policy. Errors use the RESAAS contract `{"error": {code, message, details}}`;
the codes are listed in each section below (e.g. `invalid_exam_state`,
`result_already_validated`, `empty_result`, `result_patient_mismatch`).

## Permissions by profile

From `saude/profiles.py` (the source of truth; applied by `migrate`;
`revoke` takes a permission away explicitly):

| Capability | Receptionist | Technician | Scientist | Doctor | Patient |
|---|:-:|:-:|:-:|:-:|:-:|
| create request | ✓ | - | - | ✓ | - |
| laboratory check-in | ✓ | ✓ | ✓ | ✓ | - |
| collect, reject sample | - | ✓ | ✓ | ✓ | - |
| start processing, cancel exam | - | ✓ | ✓ | - | - |
| record result | - | ✓ | ✓ | ✓ | - |
| validate, release, amend | - | - | ✓ | **revoked** | - |
| configure parameters / reference ranges | - | view | ✓ | view | - |
| patient history, evolution, consultation panel (`lab_evolution_paciente`) | - | - | ✓ | ✓ | - |
| own exams, results, trends (portal) | - | - | - | - | ✓ |

Nobody hard-deletes a result value; a validated result is never deleted by
anyone (enforced in code, `409`). Frontend buttons follow these permissions for
UX only; the backend decides.

## Multi-tenancy and scope

- Every laboratory queryset is limited to the signed context's **Entity and
  Branch** (BaseAPIView). A patient's laboratory history, evolution and
  consultation summary include all Branches of the Entity (the patient record is
  Entity-wide; decision of the domain-model phase).
- Ids in a payload are resolved inside the Entity: patient, consultation, exam
  item (`TenantRelationsMixin` for every relation). An item never moves to
  another request, and a result always belongs to its item's patient.
- The patient portal derives the patient from the authenticated user; a patient
  id sent by the client is ignored.

## Troubleshooting

| Symptom | Check |
|---|---|
| A lab button is missing | the user's effective permission (table above); `migrate` applied the profile changes; the frontend reloaded the user's permissions |
| `403 Permission Is Not Defined For This Action` | the action has no permission on an old deployment: deploy the release and run `migrate` (action permissions are synced on migrate) |
| `409 invalid_exam_state` | the exam's current state does not allow the action (see *Workflow*); a cancelled exam accepts nothing |
| `409 result_already_validated` on save / delete | validated results are immutable: amend it |
| `400 empty_result` on validate | record values, a value, a report or a file first |
| `400 result_patient_mismatch` | the result's `paciente` must be the exam request's patient (omit it: the server fills it) |
| A parameter has no chart | it is not numeric, `graphable` is off, or it has fewer than 2 validated values |
| No flag on a value | no reference range matches the patient's sex/age (ranges are configuration; nothing is defaulted) |
| The patient does not see a result | it is not released, the parameter is not `patient_visible`, or the patient has no portal access in this Entity |
| A new action/screen is not visible in dev/front | restart `quasar dev` (new routes); after a quasar_resaas change: `rm -rf node_modules/.q-cache .q-cache` first |


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
- **Collection**: the `collect` action sets `colhido`, `data_colheita` and
  `collected_by` (see *Collection and sample rejection*).
- **The exam state is read-only in the API** (`estado_exame`, since lab phase 9):
  a `PATCH itempedidoexamemedicos/{id}/` ignores it (other fields, e.g.
  `observacao`, are still saved). It changes only through the laboratory actions
  (`collect`, `reject_sample`, `start_processing`, `cancel`), each with its own
  permission and audit. *Deprecated:* setting `estado_exame` by PATCH (no screen
  did it); before, a PATCH to `colhido` also stamped `data_colheita` - that path
  is gone.
- **Laboratory waiting time** = `checked_in_at -> first data_colheita` of the
  request (or up to now while nothing is collected).

Results (`ResultadoExameMedico`):

- Recording needs `add`/`change_resultadoexamemedico`. **Validating needs
  `validate_resultadoexamemedico`** and happens **only** through
  `POST /api/saude/resultadoexamemedicos/{id}/validate/` (`@resaas_action`).
  Since lab phase 10 `validado` is **read-only** in the API: a `validado: true`
  in a create/update payload is ignored. *Deprecated path, migrated:* the result
  screen (`ResultadopedidoexamemedicoSEPage.vue`) had a "Validated result"
  switch; it now shows the state and a *Validate* button (shown with the
  permission) that calls the action.
- **A result belongs to the patient of its exam item** (lab phase 9, both the
  generic `POST`/`PATCH resultadoexamemedicos/` and the services): without
  `paciente` the server takes the item's request patient; a different patient is
  `400 result_patient_mismatch` (`error.details.paciente`), also when a `PATCH`
  tries to move it. A parent folder (`pai`) of another patient is
  `400 folder_of_another_patient`. (`TenantRelationsMixin` already rejects an
  item or patient of another Entity.)
- `validado`, `validado_por` and `data_validacao` are always set by the server
  (read-only in the API).
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
| `data_type` | `decimal`, `integer`, `text`, `boolean` (yes/no), `choice` (positive/negative, blood group, ...), `date` |
| `decimal_places` | `decimal` only: the most decimal places a value may have |
| `choices` | `choice` only: the allowed values, e.g. `["Positive", "Negative"]` |
| `required`, `active` | an inactive parameter disappears from new forms; old values keep their snapshot |
| `patient_visible` | shown to the patient once released (patient portal) |
| `graphable` | offered as a time series (doctor's evolution, patient's trends); default `true` |

A parameter can be charted when it is numeric (`decimal`, `integer`) **and**
`graphable` (`ExamParameter.is_graphable`). Migration `saude 0011` added
`graphable` and set it to `false` on the existing non-numeric parameters, so
nothing that was charted before stops being charted.

Values are stored by type in `ResultParameterValue`: `value_numeric`,
`value_text` (text, choice), `value_boolean` and `value_date` (`date`
parameters; migrations `saude 0011` and `0012`). A `date` value is sent as
`YYYY-MM-DD`; anything else is `400 invalid_result_values` with the message
"Enter a valid date (YYYY-MM-DD)." on that parameter. A `date` parameter is
never charted.

Where `graphable` applies (all filtered in the database, never in the browser):

| Consumer | Effect |
|---|---|
| `GET .../itempedidoexamemedicos/{id}/result_form/` | each parameter has `graphable` |
| `GET .../pacientes/{id}/lab_parameters/` | `graphable` per parameter (a value whose parameter was deleted: its numeric snapshot decides) |
| `GET .../pacientes/{id}/lab_evolution/` | `parameter.graphable`; the points and the comparison are still returned (table), the frontend draws the chart only when `true` |
| Patient portal `trends` | only graphable parameters are offered, and the series of a non-graphable one is empty |

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

**Configuration screens (dev/front).** Menu *Exams -> Exam Parameters*
(`list_examparameter`, `src/pages/saude/examparameter/ExamparameterLPage.vue`)
and *Exams -> Exam Reference Ranges* (`list_examreferencerange`,
`ExamreferencerangeLPage.vue`). Both are the generic `s-auto-crud` (list,
create, edit, delete as the permissions allow): no form per exam type. `choices`
is a JSON field, typed as a JSON list (`["Positive", "Negative"]`) and validated
as JSON by the form and by `ExamParameter.clean()` on the server. The routes are
PROTECTED by `list_examparameter` / `list_examreferencerange` (and the API by
BaseAPIView's per-action permissions), granted to the Medical Laboratory
Scientist. A Technician sees the parameters inside the result form
(`view_examparameter`) but cannot list or configure them (`403`).

### Standard catalogue (`seed_exam_catalogue`)

A new Entity does not have to build its catalogue by hand:

```bash
python manage.py seed_exam_catalogue --entity Amal --dry-run   # validate and count, write nothing
python manage.py seed_exam_catalogue --entity Amal             # --branch <name|id> when it has several
```

It creates about 165 exams with their parameters (code, type, unit, decimal
places, choices, required), organised as:

| Type | Classes |
|---|---|
| Laboratório | Hematologia, Hemostase, Imuno-hematologia, Bioquímica, Endocrinologia, Marcadores tumorais, Imunologia e serologia, Biologia molecular, Microbiologia, Parasitologia, Urina, Líquidos biológicos, Anatomia patológica |
| Imagiologia | Radiologia, Ecografia, Tomografia computorizada, Ressonância magnética, Mamografia, Densitometria óssea |
| Exames funcionais | Cardiologia, Pneumologia, Neurofisiologia, Audiologia |
| Endoscopia | Endoscopia digestiva |

- **Real configuration, safe in production.** Additive and idempotent: types and
  classes are matched by name, exams by name (unique per Entity), parameters by
  `code`. Only what is missing is created; nothing existing is changed or
  deleted. An exam the laboratory renamed, moved, deactivated or edited keeps its
  configuration, and only gains the parameters it is missing.
- **Tenant explicit.** `--entity` is required; `--branch` too when the Entity has
  several Branches. Nothing is written to another Entity.
- **No reference ranges, no critical limits.** Reference intervals depend on the
  method, the analyser and the population and must be verified by each
  laboratory (CLSI EP28, ISO 15189). Until the laboratory adds them, values are
  recorded without a flag (see above).
- **Language.** Names, units and choices are Entity data shown as-is on the
  request and result screens. The standard catalogue is written in Portuguese
  (Mozambique); the laboratory can rename or extend it on the existing screens.
- **Codes.** `ExameMedico.codigo` is the catalogue's internal code (`HEM-01`,
  `BIO-15`, ...), not a LOINC code. Terminology mappings are future work.

Code: `saude/services/catalogos/exam_catalogue.py` (data),
`saude/services/exam_catalogue_service.py`,
`saude/management/commands/seed_exam_catalogue.py`.
Tests: `saude/tests/test_exam_catalogue.py`.

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

### Free-form report (the second way)

The result screen (`AddResultadoModal.vue`, "Results" of an exam request) offers
both ways on each exam's card, on the **same** result record (the item's current
revision):

- **Record result** opens the structured form above (`record_result`).
- The card itself takes a free-form report: a value, findings, an observation
  and/or an attached file (PDF, image, ...), saved with
  `POST .../{id}/record_report/` (multipart: `valor_resultado`?, `laudo`?,
  `observacao`?, `file`?), under the same permission
  `record_result_itempedidoexamemedico`.

`record_report` creates the result header when there is none (type `File`,
revision `N+1`, patient and exam name from the item, collection time from the
item, result time = now) or updates the current draft. It never touches the
structured values, and `record_result` keeps the report text, so an exam can
have both. The same rules apply: a validated result answers
`409 result_already_validated` (amend it), a request with nothing to save
`400 empty_result`, a value longer than 200 characters `400 invalid_result_values`,
and an item of another Entity `404`. Each recording is audited
(`LAB_RESULT_RECORDED`). Validate and Release are shown on the card only in the
state and with the permission the backend accepts.

### Validation, release, amendment

| Step | Endpoint | Permission | Rule |
|---|---|---|---|
| Record | `record_result` (structured) or `record_report` (free-form) | `record_result_itempedidoexamemedico` | draft, editable |
| Validate | `resultadoexamemedicos/{id}/validate/` (the only path) | `validate_resultadoexamemedico` | transaction + row lock (two clicks validate once: `409 result_already_validated`); needs content - structured values, a value, a report or a file (`400 empty_result`); **completes the exam item** (`concluido`); then immutable |
| Release | `resultadoexamemedicos/{id}/release/` | `release_resultadoexamemedico` | only after validation; `released`, `released_by`, `released_at` set by the server and read-only in the API |
| Amend | `resultadoexamemedicos/{id}/amend/` `{"reason"}` | `amend_resultadoexamemedico` | only the latest validated revision; creates revision N+1 (copy of the values, unvalidated). The validated one stays unchanged and is superseded. The exam item goes back from `concluido` to `processamento` until the new revision is validated. The new revision also keeps the free-form value (`valor_resultado`) and the attachment (same stored file); before lab phase 10 they were dropped. |

`numero_revisao` of a structured result is set by the server. History and
evolution use only the **latest revision of each exam item**. A superseded
revision is the record of the correction, not a second measurement. Recording,
validation, release, amendment, collection and rejection are written to the audit
log (`LAB_RESULT_RECORDED`, `LAB_RESULT_VALIDATED`, `LAB_RESULT_RELEASED`,
`LAB_RESULT_AMENDED`, `LAB_SAMPLE_COLLECTED`, `LAB_SAMPLE_REJECTED`), with
`details`: validate `{"revision", "item_from"?, "item_to"?}`, release
`{"revision"}`, amend `{"reason", "revision", "new_revision", "item_from"?,
"item_to"?}`.

Record, validate and release are **three permissions**: none implies another
(Technician records; Scientist validates and releases; see *Laboratory profiles*).
The patient sees a result only once it is **released** - recorded or validated
is not enough (`patient_portal_service`).

A partial save of a result (validate, release) no longer re-reads its attachment
from storage (`ResultadoExameMedico.save()` only refreshes the file metadata when
`file` is saved), so a result whose file is missing from disk can still be
validated and released (it used to be a `500`).

**Legacy results** (free-text `valor_resultado`, report, PDF) are untouched and
still shown. They are never converted into structured values, so they do not
appear in evolution charts.

### Collection and sample rejection

- `POST itempedidoexamemedicos/{id}/collect/` (`collect_itempedidoexamemedico`):
  from `pendente`, `agendado` or `recolha_necessaria` to `colhido`. It sets
  `data_colheita` and `collected_by`. Audit `LAB_SAMPLE_COLLECTED`
  `{"from", "to", "collected_at"}`.
- `POST .../{id}/reject_sample/` `{"reason"}` (`reject_sample_itempedidoexamemedico`):
  from `colhido` or `processamento` to **`recolha_necessaria`**. It keeps
  `rejected_at` and `rejection_reason` on the item (the **last** rejection only).
  Audit `LAB_SAMPLE_REJECTED` `{"from", "to", "reason", "collected_at"}`: every
  rejection keeps its reason and the collection it rejected. A new `collect`
  starts again. Rejecting a sample that was already rejected is `409` (collect
  it first). No reason: `400 rejection_reason_required`.
- Both run in a transaction with the item row locked (`select_for_update`): two
  clicks collect or reject once; the second is `409 invalid_exam_state`.
- There is no separate Sample model (decision of lab phase 2: deferred until
  tube labels / one sample shared by several exams / an external laboratory are
  needed). Collection is per exam item, so a request with several exams can
  need several samples: nothing assumes one request = one sample.

### Laboratory queue actions

All PROTECTED `@resaas_action`s on the scoped item (`get_object()`: another
Entity's item is `404`), each with its own permission, run inside a transaction
with the item row locked (`select_for_update`), and audited with `details`
(`AuditLog.details`, django_resaas):

| Action | Permission | From -> to | Errors | Audit |
|---|---|---|---|---|
| `POST pedidoexamemedicos/{id}/check_in/` | `check_in_pedidoexamemedico` | sets `checked_in_at` once | - (repeating it changes nothing and records nothing) | `LAB_CHECKED_IN` `{"checked_in_at"}` |
| `POST itempedidoexamemedicos/{id}/start_processing/` | `start_processing_itempedidoexamemedico` | `colhido` -> `processamento` | `409 invalid_exam_state` from any other state | `LAB_PROCESSING_STARTED` `{"from", "to"}` |
| `POST itempedidoexamemedicos/{id}/cancel/` `{"reason"}` | `cancel_itempedidoexamemedico` | `pendente`, `agendado`, `colhido`, `processamento`, `recolha_necessaria` -> `cancelado` | `400 cancel_reason_required`; `409 invalid_exam_state` when completed or already cancelled | `LAB_EXAM_CANCELLED` `{"from", "to", "reason"}` |

A cancelled exam cannot be collected any more (`409`). Granted to the Medical
Laboratory Technician and Scientist (`saude/profiles.py`). In the exam items list
(`ItemPedidoexamemedicoLPage.vue`) *Start processing* runs by itself
(`autorequest`); *Cancel exam* asks for the reason (`sDialog` prompt).

The **Laboratory Queue** widget (`saude.lab.queue`) has a *Patient arrived at the
laboratory* row action (`type: "request"`, `check_in_pedidoexamemedico`), shown
only on rows whose `checked_in` is `"no"` (a machine value on each row, not a
column). Laboratory waiting (check-in -> first collection) stays separate from
the doctor's waiting time.

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
  has validated values for, marked `graphable` (numeric and graphable).
- `GET /api/saude/pacientes/{id}/lab_evolution/?parameter=<code>&from=&to=`:
  `{"parameter": {code, name, unit, numeric, graphable}, "points": [{result, date, value, unit, reference, flag}], "comparison": {current, previous, change}}`.
  Only validated results, the latest revision of each item, ordered by result
  date, filtered in the database. Values only, with no interpretation.
- `GET /api/saude/pacientes/{id}/lab_history/?exam=<id>&parameter=<code>&from=&to=&page=&page_size=`
  (lab phase 11): the patient's **validated** exam results, latest revision of
  each exam item, newest first:
  `{"results": [{id, exam: {id, name}, date, revision, released, validated_at, value, values: [{code, name, value, unit, reference, flag}]}], "pagination": {page, page_size, total}}`.
  `values` is the **snapshot** recorded with the result (renaming a parameter or
  changing its reference later never changes it). Filters and pagination run in
  the database; `page_size` defaults to 20 and is capped at 50. A date that is
  not `YYYY-MM-DD` or an invalid exam id is `400` (also in `lab_evolution`,
  where an unparseable date used to be silently ignored).
- All three are **PROTECTED** by `lab_evolution_paciente`. The patient is the URL
  resource (`get_object()`, scoped to the current Entity/Branch), so another
  Entity's patient is `404`. Values are limited to that patient and to the
  current Entity (all its Branches: lab phase 2 decision).
- `GET /api/saude/itempedidoexamemedicos/{id}/trail/` (**PROTECTED**,
  `view_itempedidoexamemedico`; another Entity's item is `404`): the exam's audit
  trail, oldest first - `[{action, at, by, details}]` with the request's
  laboratory arrival, collections, rejections (with their reason), processing,
  cancellation and its results' recording, validation, release and amendment.
  Read from `AuditLog` (`details`) inside the current Entity; nothing is stored
  twice.
- Frontend: *Lab history* button next to *Lab evolution* on the patient record
  (`LabHistoryDialog.vue`, parameter and date filters, *Load more*), and *Exam
  trail* in the exam items list (`ExamTrailDialog.vue`, a client-only
  `extraActions` entry of `s-auto-crud`; shown with `view_itempedidoexamemedico`).

### Frontend (`dev/front`)

- `pages/saude/components/ExamResultDialog.vue`: one generic form for every
  exam, built from `result_form`: numbers, text, choice (select), yes/no
  (toggle), the unit as a suffix, the reference as a hint, flags. It becomes
  read-only once validated, and shows server field errors on each field. An exam
  without parameters records only the observation and the report. Opened from
  the results dialog (`AddResultadoModal`, "Record result" per exam).
- `pages/saude/components/LabEvolutionDialog.vue`: pick a parameter and a
  period. It shows the comparison (previous, current, change), a line chart
  (the engine's `LineChartWidget`; only **graphable** parameters with 2 or more
  points) and the table of points. Opened from the patient record ("Lab
  evolution" button, shown with `lab_evolution_paciente`).

#### Doctor integration (lab phase 13)

- **Consultation panel** `pages/saude/components/LatestLabResults.vue`, under
  *Latest vital signs* on the consultation form (`ConsultaSEPage.vue`; mounted
  only with `lab_evolution_paciente`, UX). Buttons open *Lab evolution* and *Lab
  history* for the same patient.
- `GET /api/saude/pacientes/{id}/lab_summary/` (**PROTECTED**,
  `lab_evolution_paciente`; the patient is `get_object()`: another Entity's is
  `404`), `lab_result_service.doctor_summary`:

  ```json
  {"pending": [{"id", "exam", "state", "state_label", "priority", "requested_at"}],
   "recent":  [{"id", "exam", "released_at", "new", "value",
                "values": [{"code", "name", "value", "unit", "reference", "flag",
                            "previous", "previous_date", "change"}]}]}
  ```

  - `pending`: the patient's open exam items - `pendente`, `agendado`, `colhido`,
    `processamento`, `recolha_necessaria` - whoever requested them (doctor request
    or exam only), oldest first, at most 20.
  - `recent`: the 5 latest **released** results (released = made available to the
    requester; validated-only results are not shown here), latest revision of each
    exam item. `new` = released in the last 7 days. Each structured value carries
    the previous **released** value of the same parameter code and the numeric
    `change`.
  - A fixed number of queries whatever the number of results
    (`DoctorLabSummaryTests.test_queries_do_not_grow_with_the_number_of_results`).
- **No interpretation or diagnosis** is produced: the panel shows values,
  previous values, change and the laboratory's configured reference/flag.
- Already in place before this phase: the Doctor dashboard's *Pending Exams*
  (count of open items of the doctor's own consultations) and *Recent Exam
  Results* (released results of exams the doctor requested, last 7 days).

#### Charts (lab phase 12)

- **Source:** only the structured values the backend returns (`lab_evolution`,
  portal `trends`), i.e. `ResultParameterValue.value_numeric` of validated results
  (released, for the patient). A legacy free-form result - a number typed in
  `valor_resultado`, a report or a PDF - is never parsed into a point
  (`EvolutionTests.test_charts_come_only_from_structured_values`).
- **Which parameters:** numeric **and** `graphable` (see *Exam definition*). A
  non-graphable parameter keeps its table, without a chart.
- **Shared helper** `pages/saude/components/labChart.js` (`labChartData`,
  `labChartOptions`), used by `LabEvolutionDialog.vue` and the patient's
  `MyHealthPage.vue`: one series, one y axis titled with the unit, and the
  **reference** of the latest point (its snapshot) as a neutral band between low
  and high - or a dashed line when only one limit exists, nothing when none is
  configured. Points carry their own reference and flag in the table; the chart
  never colours or interprets them.
- It passes the band to the chart through quasar_resaas `LineChartWidget`'s
  `options` prop (ApexCharts options; optional, dashboards unchanged).

### Security audit (lab phase 16)

`saude/tests/test_lab_security_audit.py` tries to break the laboratory by
changing ids by hand. Every case fails closed:

| Attack | Result |
|---|---|
| Another **Entity**'s item / result / patient on any lab action (result form, record, collect, cancel, trail, validate, release, amend, history, summary, evolution) | `404`, nothing changes |
| Another **Branch** of the same Entity (item) | `404` (BaseAPIView scope) |
| Validate without `validate_`, release without `release_`, amend without `amend_` | `403` - record, validate and release stay separate |
| `PATCH` an exam item's `pedido` to another patient's request | `400` (`error.details.pedido`) - would have moved the exam and its results to another patient |
| `PATCH` an exam item's `exame` after collection or once it has a result | `400` (`error.details.exame`) |
| A result pointing to another Entity's exam item | `400` (`TenantRelationsMixin`) |
| `DELETE` / explorer `delete` (trash) / `hard_delete` of a **validated** result, or of an exam item with a validated result | `409 result_already_validated` / `exam_has_validated_result` - corrected by amending, never deleted. An unvalidated draft can still be deleted |
| Record (`record_result`, `record_report`) or validate for a **cancelled** exam | `409 invalid_exam_state` |
| One patient's history / consultation summary showing another patient's results or pending exams | never |
| Patient portal: another patient's data, unreleased results, non-visible parameters | never (`PortalDataTests`) |

Fixed in this phase (they were possible before): moving an item to another
request, changing its exam after collection, deleting/trashing/hard-deleting a
validated result (or its item), and recording/validating for a cancelled exam.

### Performance (lab phase 17)

Measured first (test database, one patient with 10 and then 20 released
results, plus open exams of other patients), optimised only where the
measurement showed a problem:

| Endpoint | Queries (N=10 -> N=20) | Note |
|---|---|---|
| Laboratory widgets (queue, attention, TAT, waiting, results to validate) | 4-7, constant | queue page-limited |
| `lab_parameters`, `lab_evolution`, `lab_history`, `lab_summary`, `result_form`, `trail` | 11-15, constant | `lab_history` paginated (20, max 50); `lab_evolution` returns the whole series of one parameter unless `from`/`to` are given (by design: the evolution is the series) |
| **Exam items list** (`itempedidoexamemedicos/`) | **146 -> 12** per page | was one query per relation label of every row and per latest result |
| **Results list** (`resultadoexamemedicos/`) | **71 -> 11** per page | same, plus two `COUNT`s per row for `children_count` / `has_children` |

What changed (no index or schema change was needed):

- `ItemPedidoExameMedicoAPIView.queryset`: `select_related` of every relation the
  serializer labels (entity, branch, users, exam, request -> patient -> person)
  and a `Prefetch` of the results (latest first, `to_attr="results_latest_first"`),
  which `ItemPedidoExameMedicoSerializer.get_resultado` uses when present.
- `ResultadoExameMedicoAPIView.queryset`: `select_related` of the labelled
  relations and an annotated `_children_count`;
  `ResultadoExameMedico.children_count` uses it when the row is annotated (a query
  otherwise, so other callers are unchanged).
- Guard: `LabQueryBudgetTests` - a list page's number of queries must not grow
  with its rows. `DoctorLabSummaryTests` guards `lab_summary` the same way.

The remaining ~10 queries of any request are the tenant context and permission
checks of the framework, the same for every endpoint.

### Laboratory profiles (defaults)

| Permission | Technician | Scientist |
|---|:-:|:-:|
| `collect_itempedidoexamemedico`, `reject_sample_itempedidoexamemedico`, `record_result_itempedidoexamemedico`, `view_examparameter` | yes | yes |
| `validate_resultadoexamemedico`, `release_resultadoexamemedico`, `amend_resultadoexamemedico` | - | yes |
| `list/add/change_examparameter`, `view/list/add/change_examreferencerange`, `lab_evolution_paciente` | - | yes |

The Doctor profile has `lab_evolution_paciente` and `record_result_itempedidoexamemedico`
(recording), but **not** validating, releasing or amending a lab result: those
are the laboratory's. Nobody hard-deletes a result value
(`hard_delete_resultparametervalue`): a recorded value is corrected by amending
the result. `saude/profiles.py` takes these away with `revoke` (Doctor:
`validate_`, `release_`, `amend_`, `hard_delete_resultadoexamemedico`,
`hard_delete_resultparametervalue`; Scientist: `hard_delete_resultparametervalue`),
also where an earlier profile file or the database had granted them. It is
applied by `python manage.py migrate` (dev) and with the release + `migrate` (pro).
Tests: `LabPermissionsSeparationTests` (`test_structured_lab_results.py`).

### Known limitations (not implemented)

- Patient area: see *Patient portal* in
  [Health operational dashboards](health-operational-dashboards.md#patient-portal)
  (released results and trends only). The patient **cannot download** a released
  result's attachment or PDF yet.
- No Sample model (tube labels, one sample for several exams, external
  laboratory): deferred until required.
- No unit conversion, and no critical-result notification workflow beyond the
  dashboard's *Attention Required* list.
- History/evolution for staff with `lab_evolution_paciente` include validated
  results that are not released yet (the laboratory needs them); the doctor's
  consultation panel and the patient show released results only.
- `saude` migrations are not versioned in git in dev/back (`.gitignore`), and
  pro has its own migration history: data steps inside a `saude` migration (e.g.
  0011's `graphable` defaults) do not reach pro. Harmless for 0011 (`is_graphable`
  requires a numeric parameter); a future data migration needs a management
  command or an aligned migration history.
- Profile clean-up proposed, not applied: the Doctor holds `delete`/`hard_delete`
  of exam parameters and reference ranges, and the Scientist
  `hard_delete_resultadoexamemedico` (validated results are protected in code
  anyway).

## Exam request screens (dev/front)

### Exam request view (`view_pedidoexamemedico`) for the laboratory

- `GET pedidoexamemedicos/{id}/items/` (the request's exams with their results,
  used by the results upload: `AddResultadoModal`, `RightMenu`) is protected by
  `view_pedidoexamemedico`. It was a plain `@action` with no permission, which
  `BaseAPIView` refuses to everyone but Root (403 "Permission is not defined
  for this action").
- The request answers `patient_id` (read only): its own patient (direct
  request) or its consultation's. `PedidoexamemedicoVPage` passes it to the
  patient header - the route `:id` is the request, not the patient.
- Both laboratory profiles hold `list_resultadoexamemedico`, required by the
  results list page (`list_resultadopedidoexamemedico` route).
- `resultadoexamemedicos/explorer/` (folders and files of results, the results
  list page) needs `list_resultadoexamemedico`; creating a folder / file through
  it (POST) also `add_resultadoexamemedico`. The explorer's other actions have
  explicit permissions too: rename / move / favourite `change_`, delete
  `delete_`, breadcrumb / download / preview / info `view_`, trash / favourites
  `list_resultadoexamemedico`. All were plain `@action`s (403 to everyone but
  Root).
- The other former plain `@action`s now carry their own permission
  (`resaas_action(permission=...)`):

  | Endpoint | Permission |
  |---|---|
  | `consultas/{id}/historico/` (the patient's other consultations) | `list_consulta` |
  | `consultas/paciente/{paciente_id}/` | `list_consulta` |
  | `consultas/iniciar/` (POST: consultation from an appointment) | `add_consulta` |
  | `diagnosticos/consulta/{id}/` | `list_diagnostico` |
  | `episodiosclinicos/consulta/{id}/` | `list_episodioclinico` |
  | `procedimentos/consulta/{id}/` | `list_procedimento` |
  | `pedidoexamemedicos/{id}/resultados/` | `list_resultadoexamemedico` |

  Fixed on the way: `historico` and `paciente` read `Consulta.objects` (other
  Entities / Branches) - now the tenant-scoped queryset; `iniciar` took an
  appointment of any tenant by id, read a non-existent `agenda.employee` and
  wrote an invalid state - now the caller's Entity/Branch only (404 otherwise),
  `agenda.medico`, `"concluida"`; `diagnosticos/.../consulta/` failed
  (`Response` imported inside the class). The unimplemented stubs
  `consultas/{id}/receitas|exames|transferencias|relatorios/` (`pass`, 500) were
  removed: those documents are listed with `?consulta=` (ConsultationDocumentsList).
  Tests: `saude/tests/test_protected_consultation_actions.py`.
- The results list page (`list_resultadopedidoexamemedico`) shows only the
  **current patient's** results - the patient of `pacienteStore` (`Paciente.row`,
  persisted, as the other clinical pages); with none open it says so. The
  explorer always sends `paciente`, and the backend requires it:
  `explorer/` without `paciente` is `400 patient_required`, a patient of
  another Entity `404 patient_not_found`; a created folder / file is the
  patient's, and a folder inside another patient's folder is
  `400 folder_of_another_patient`. File upload sends multipart (it used to send
  `file: undefined` in JSON, so no file was ever stored). After an upload the
  list reloads and the new file opens in the preview at once.
- `ExplorerItem.vue` reads `tipo` as the choice the API returns
  (`{id: 'Folder'|'File'}`) and takes the icon from the serializer's `icon`;
  it used to call `.toLowerCase()` on the `file` object, which threw and left
  those files out of the grid.
- On the results list page (`list_resultadopedidoexamemedico`), clicking a
  file opens `FilePreviewDialog.vue` (full screen): image, PDF and text in
  place, video / audio with their players, anything else offers the download;
  the bar has "open in a new tab" and "download". The type comes from the
  item's `mime_type` / `extensao`; the URL is the stored media file the
  explorer already returned (nothing else is fetched). Media files are served
  without `X-Frame-Options`, so PDFs and text show in an iframe.
- Tests: `saude/tests/test_laboratory_flow.py` (`ExamRequestItemsTests`,
  `ResultsExplorerPermissionTests`).

### Exam request page (`add_pedidoexamemedico`): add buttons follow the permissions

`PedidoexamemedicoSEPage.vue` shows each add button only with its own
permission (UX only - every endpoint checks again):

| Button | Shown / enabled with |
|---|---|
| Add exam type | `add_tipoexamemedico` |
| "+" on an exam type (add a class) | `add_classeexamemedico` |
| "+" on an exam class (add an exam) | `add_examemedico` |
| Save request | `add_pedidoexamemedico` **and** `add_itempedidoexamemedico` (the request and its items are separate POSTs) |

Without a catalogue permission the "+" is replaced by a plain icon, so the
catalogue still reads the same.

Each added exam shows its **priority** as three buttons (Normal grey, Urgent
orange, Very urgent red) and, folded under "Instructions and notes", its
instructions and notes; with more than one exam a control above the list sets
the priority of all of them. They are sent per item
(`itempedidoexamemedicos/`: `prioridade` `normal|urgente|muito_urgente`,
`instrucoes`, `observacao`) - before, the form holding them was never on the
page, so every exam went as Normal. While searching the catalogue, every type
and class found opens and the matching text is highlighted (`s-highlight`).
