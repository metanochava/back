# ReSaaS Ensino: from `ensino` to four apps

Progress report of the restructuring of the `ensino` module into `academica`,
`pedagogica`, `laboratorios` and `administrativa` (started 2026-11-14).

| Checkpoint | State |
|---|---|
| 0 Audit | done (this file) |
| 1 Architecture | done (this file). The owner said to go ahead: rename strategy as proposed, no commit, Lab Manager not located (null adapter) |
| 2 `ensino` → `academica` | **done in dev**, 2026-11-14 |
| 3 Academica | **done in dev**: timetables, PDFs, transfers, prior schooling, year-end |
| 4 Pedagogica | **done in dev**: digital board, plans, materials, assignments / submissions, calendar, progress notes, messages, portal |
| 5 Laboratorios | **done in dev**: rooms, workstations, equipment, networks, environments, lab sessions, seats, exercises, audited remote access, Lab Manager null adapter |
| 6 to 9 | not started |

## 0. Audit (2026-11-14)

### Repositories

| Repo | Branch | HEAD | Local changes |
|---|---|---|---|
| dev/back | develop | `9cdba8d` Merge tag v1.0.113 | 30 modified, 12 new |
| dev/front | main | `821eae1` release v0.0.93 | 19 modified, 18 new |
| lib/django_resaas | develop | `1529f18f` (0.0.685) | 17 modified, 8 new |
| lib/quasar_resaas | main | `0d75520b` (0.0.1493) | 10 modified, 4 new |

Most local changes are uncommitted work of 2026-11-12/14:

- the point of sale, open tabs and hospitality;
- the authentication phases 0 to 3;
- the ensino portal and the record pages.

**Risk:** restructuring `ensino` on top of them mixes two changes in one
diff.

### The `ensino` app today (dev/back/ensino, ~2,300 lines + tests)

| Area | Models | Services / API |
|---|---|---|
| Structure | GradingScale, EducationLevel, Programme, GradeLevel, Subject, CurriculumItem, AcademicYear, AcademicPeriod | CRUD (views/structure.py) |
| People and enrolment | ClassGroup, Student (→ Person), Guardian (Student ↔ Person, payer), Enrolment, EnrolmentStatusChange | student_service, enrolment_service (enrol, status transitions, class change, history) |
| Academic | TeachingAssignment (→ hr.Employee), Assessment, Grade, GradeRevision, StudentAttendance | grading_service (record, amend with reason, report card) |
| Fees | TuitionRule (→ catalog item), TuitionCharge (→ draft sale) | tuition_service (catalog + sales public services, optional) |
| Portal | none | portal_service: the student / guardian sees only their own enrolments, grades, attendance and fees |

Also:

- 19 `@resaas_action`s;
- profiles School Secretary, Academic Director, Teacher, Student, Guardian
  and Admin (`profiles.py`);
- sidebar, pt-pt translations;
- tests `test_enrolment`, `test_academic`, `test_portal`;
- `docs/modules/ensino.md`.

**Frontend** (`dev/front/src/pages/ensino`):

- `EnsinoCrudPage`, the student registration page and the portal
  `MySchoolPage`;
- the record pages (`views.js`, 18 models);
- the routes are spread in `router/routes.js`.

**Dependencies:**

- `ensino` uses:
  - `django_resaas` (Person, Entity/Branch, BaseModel/BaseAPIView,
    profiles);
  - `hr.Employee` (teachers);
  - `catalog` / `sales` public services (fees, optional).
- No other app imports `ensino`.

**Data:**

| Environment | Data |
|---|---|
| dev | demo data of "Machava" (6 students and guardians, 6 enrolments, 16 grades, 20 attendance records, 18 fees) |
| pro | `ensino` installed, all tables empty (0 rows) |

Migrations are not versioned: each environment generates its own.

**Already in place:**

- structure, students, guardians and enrolments with an auditable history;
- teaching assignments, assessments and grades with audited amendments;
- attendance;
- fees billed through sales;
- the student / guardian portal;
- the record pages.

**Missing** (asked for):

- timetables;
- report card / certificate PDFs;
- transfers between institutions;
- year-end progression;
- everything of pedagogy, laboratories and administration;
- the Form Engine form `school.enrolment`, defined but not wired.

**Lab Manager:** not found on this server. No folder, no container, and `gh`
is not authenticated to search GitHub. Its real architecture could not be
analysed.

### Architectural problems found

1. One app holds what the request splits in four: academic records,
   portal and fees together.
2. Guardians are academic data (who may see a student, who pays) but the
   request puts guardians under administration. They need a single owner
   (decision in §1).
3. Rooms do not exist (the timetables and laboratories need them).
4. Documents, admissions and requests do not exist. They must reuse the
   core documents, the Form Engine and workflow, not new mechanisms.

## 1. Architecture (proposal)

### Single source of truth

| Data | Owner | Others use |
|---|---|---|
| Person (identity of student, guardian, teacher) | django_resaas core | everyone, by id |
| Employee (teacher, lab staff) | hr | academica, pedagogica, laboratorios |
| Structure, years, periods, classes, subjects, students, guardians, enrolments, timetables, attendance, assessments, grades, report cards, transfers, progression | **academica** | the others through `academica.services` (public functions) and events |
| Lesson plans, lessons (digital board), materials, assignments, submissions, pedagogical calendar, progress notes, messages to a class | **pedagogica** | laboratorios (exercises of a session) |
| Rooms and laboratories, workstations, equipment (an inventory item by id), networks and environments, practical sessions, student ↔ workstation, remote access (granted, logged, audited), Lab Manager adapter | **laboratorios** | academica (a timetable slot's room, by id) |
| Admissions (Form Engine), student documents (core documents), service requests (workflow), declarations and certificates issued, institutional communication | **administrativa** | academica (an accepted admission becomes a student and an enrolment through `academica.services`) |
| Products and prices; stock (books, equipment, consumables); fees, invoices, payments | catalog; inventory; sales | through their public services only |

**Guardians:** the model stays in `academica`. It decides who may see a
student and who pays. `administrativa` manages them in its screens through
`academica.services`, so there is never a second guardian record.

### Dependency direction (no cycles)

```
administrativa ─┐
laboratorios  ──┼──> academica ──> hr, catalog?, sales?, django_resaas
pedagogica    ──┘        ^
laboratorios  ──> pedagogica (exercises), inventory? (equipment)
```

- `academica` imports none of the three. They react to its events:
  - `academica.enrolment.activated`
  - `academica.enrolment.transferred`
  - `academica.grade.published`
  - `academica.student.registered`
- The three emit events too:
  - `pedagogica.lesson.published`
  - `pedagogica.submission.graded`
  - `laboratorios.session.started`
  - `laboratorios.remote_access.started`
  - `administrativa.admission.accepted`

### `ensino` → `academica` without losing data

| Step | What |
|---|---|
| a | The code moves to a new app `academica` (models, services, views, tests, profiles). Every model keeps its table (`Meta.db_table = "ensino_<model>"`), so ids, rows and relations stay where they are |
| b | A management command, idempotent and reversible, renames the app label in `django_content_type` (`ensino` → `academica`), so the permissions and every group's assignments stay attached. It also renames the App catalogue row (`ensino` → `academica`), so the Entity / EntityType activations stay |
| c | `makemigrations academica`, then `migrate academica --fake-initial`: the tables already exist, so nothing is created or dropped |
| d | `ensino` is removed from `MY_APPS` only after (b) and (c), with the tests green, in dev first. Pro is empty: the same steps, no data to move |
| e | Route names (`view_own_enrolment`, `list_student`, ...) and API paths keep compatibility aliases for one release (`/api/ensino/...` → `/api/academica/...`) |

### Frontend

```
src/modules/academica/       (moved from src/pages/ensino; same route names)
src/modules/pedagogica/
src/modules/laboratorios/
src/modules/administrativa/
```

Each module has `routes.js`, `pages/`, `components/` and `stores/` (BaseStore),
spread in `router/routes.js`.

**Dashboards and menus by permission:**

- Direction;
- Secretariat;
- Teacher;
- Student;
- Guardian;
- Laboratory manager.

Forms beyond CRUD use the Form Engine (admission wizard, enrolment).

### Lab Manager

`laboratorios.integrations.labmanager`:

- a `LabManagerAdapter` interface: list images, networks and machines;
  start / stop an environment; open a remote session;
- a null adapter (nothing configured) and an HTTP adapter written against
  the real Lab Manager API once it is located.

**Remote access:**

- an explicit grant by an authorised teacher, for one session and with a
  time limit;
- the student sees that the session is open;
- start and end are logged (who, when, which machine, why);
- never hidden.

## Decisions waiting for the owner

1. **The rename strategy above** (keep the `ensino_*` tables, relabel
   content types and the App row, `--fake-initial`).
2. **Where the Lab Manager project is** (path or repository).
3. **Commit the current local work before the restructuring**, so the
   restructuring is its own reviewable change.

## 2. `ensino` → `academica` (done in dev, 2026-11-14)

**Backend:**

- `dev/back/ensino` moved to `dev/back/academica` (`AcademicaConfig`,
  label `academica`).
- Every model keeps its table (`Meta.db_table = "ensino_<model>"`), and the
  constraint names are unchanged.
- `MY_APPS`: `'ensino'` became `'academica'`.
- `manage.py ensino_to_academica` (`--dry-run`, `--reverse`, idempotent)
  relabelled 21 content types and the App row `ensino` → `academica`.
- `makemigrations academica` + `migrate academica --fake-initial`:
  `0001_initial` was FAKED, no table touched. The backup of the old ensino
  migrations is in the session scratchpad.
- `/api/ensino/...` → the same `/api/academica/...` view for one release
  (`academica/compat.py`, `saas/urls.py`).

**Frontend:**

- `src/pages/ensino` → `src/modules/academica`; `EnsinoCrudPage` →
  `AcademicaCrudPage`.
- The API paths are `academica/...` and the app is `academica`; the route
  names are unchanged.
- `router/routes.js` imports `academicaRoutes`.
- `components/record/views.spec.js` also reads `src/modules/*/views.js`.

**Docs:**

- `docs/modules/ensino.md` → `docs/modules/academica.md`;
- `sales.md` and `record-pages.md` updated.

**Checked in dev:**

- The data is the same as before through `academica`: 6 students, 6
  enrolments, 16 grades, 20 attendance records, 18 fees.
- The profiles keep their permissions: School Secretary 46, Academic
  Director 69, Teacher 26, Student 4, Guardian 4.
- Machava keeps `academica` active.
- `/api/ensino/students/` and `/api/academica/students/` both answer 403 to
  an anonymous caller.

**Tests:**

- `academica/tests`: **24 passed** on a fresh test database. A reused test
  database still has the old ensino tables and needs `--create-db` once.
- Front: `views.spec.js` 3 passed.
- Pages compile on the dev server.

**Pro** (empty tables), same steps: deploy the code, `ensino_to_academica`,
`makemigrations academica`, `migrate academica --fake-initial`.

## 3. Academica (done in dev, 2026-11-14)

**Added:**

- `TimetableSlot`, `PriorSchooling` and `Enrolment.result` (migration
  `academica.0002`, additive);
- services `timetable_service`, `transfer_service`, `progression_service`
  and `documents_service` (3 PDF templates);
- actions `week`, `mine`, `report_pdf`, `sheet_pdf`, `transcript_pdf`,
  `transfer` (now with destination), `progression` and `close_year`;
- profiles and pt-pt translations;
- front: the timetable page and the prior schooling list, in the menu.

Docs: `modules/academica.md`.

**Tests:** `academica/tests/test_timetable_documents_year.py`, 9 passed:

- overlaps of class and room, back to back, end after start;
- the class week; the teacher reads but cannot write;
- the three PDFs;
- transfer out with its destination; prior schooling;
- year-end: blocked without grades, the preview writes nothing, promote and
  repeat, closed once, graduation, 403 without the permission.

## 4. Pedagogica (done in dev, 2026-11-18)

**Backend:**

- the new app `pedagogica` (`MY_APPS`), with 9 models and the services
  `lesson_service` and `assignment_service`;
- the views, with the portal routes `…/mine/`;
- profiles (Teacher, Academic Director, Student, Guardian, Admin), sidebar
  and pt-pt translations;
- migration `pedagogica.0001`.

**Front:** `src/modules/pedagogica` (the digital board with the whiteboard,
My lessons, the lists, the HTML sanitizer).

**Tests:**

- `pedagogica/tests/test_pedagogy.py`: 6 passed (fresh test database);
- `sanitizeHtml.spec.js`: 4 passed.

Docs: `docs/modules/pedagogica.md`.

## 5. Laboratorios (done in dev, 2026-11-18)

**Backend:**

- the new app `laboratorios` (`MY_APPS`), with 9 models and the services
  `session_service` and `remote_access_service`;
- `integrations/labmanager.py`: the adapter contract plus the Null adapter,
  set through `LABMANAGER_ADAPTER`;
- views, with the portal route `labsessions/mine/`;
- profiles (adds Lab Technician), sidebar and pt-pt translations;
- migration `laboratorios.0001`.

**Remote access:**

- only while the session runs, by the session's teacher, with a reason and
  for 1 to 60 minutes;
- one at a time per seat, visible to the student, audited
  (STARTED / ENDED / EXPIRED);
- a Lab Manager failure records nothing (502).

**Front:** `src/modules/laboratorios` (sessions with the seat grid and the
remote-access dialog, My lab sessions, the lists).

**Tests:** `laboratorios/tests/test_labs.py`, 6 passed.

**Known gaps:**

- the real Lab Manager client waits for the project's location and API;
- the timetable's `room_id` is not yet a validated link to `laboratorios.Room`
  (kept by id and name, as decided at checkpoint 1).

Docs: `docs/modules/laboratorios.md`.

### 5b. Lab Manager moved into laboratorio (2026-11-18)

- `laboratorios` was renamed `laboratorio` (Portuguese singular, the
  owner's rule). The empty tables were recreated; content types and the
  App row were relabelled, so the permissions were kept.
- `lab.sh` became `manage.py lab` plus `machine_service` / `docker_client`.
- The SQLite was imported into Machava / Sede, `lab-manager/` was backed up
  to `/root/backups/` and deleted, and the lab containers were deleted on
  request; the volumes are kept.
- Port 443 is no longer published.
- Tests: 11 passed.
- Docs: `docs/modules/laboratorio.md`.

### 5c. Front modules moved into src/pages (2026-11-18)

- On the owner's request `src/modules/{academica,pedagogica,laboratorio}`
  moved to `src/pages/`, like every other module; `src/modules/` no longer
  exists. The plan above (`src/modules/...`) is historical.
- `src/router/routes.js` imports from `../pages/<module>/routes`;
  `components/record/views.spec.js` only reads `src/pages/*/views.js`.
- Route names and files are unchanged.
