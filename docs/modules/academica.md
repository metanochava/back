# The `academica` module (the former `ensino`)

Education (kindergarten, school, university): the academic records of the
ReSaaS Ensino solution (with `pedagogica`, `laboratorio`, `administrativa` -
docs/progress/ensino-modular.md).

**Renamed from `ensino` on 2026-11-14** without moving any row:

- the models keep the `ensino_*` tables (`Meta.db_table`);
- `manage.py ensino_to_academica` relabels the content types (permissions and
  profile assignments kept) and the App catalogue row (activations kept);
- `migrate academica --fake-initial` records the existing tables;
- `/api/ensino/...` still answers for one release (`academica/compat.py`).

 Identity lives in
`django_resaas.Person`, teachers in `hr.Employee`, and fees go through
`catalog` / `sales` public services.

## Models

| Area | Models |
|---|---|
| Structure | GradingScale, EducationLevel, Programme, GradeLevel, Subject, CurriculumItem, AcademicYear, AcademicPeriod |
| People and enrolment | ClassGroup, Student (→ Person), Guardian (Student ↔ Person, one paying), Enrolment, EnrolmentStatusChange |
| Academic | TeachingAssignment, Assessment, Grade, GradeRevision, StudentAttendance |
| Tuition | TuitionRule (→ a catalogued item), TuitionCharge (→ a draft sale) |

Services:

- `student_service`: register a student, add guardians, find the payer.
- `enrolment_service`: enrol, change status and change class. The enrolment
  fee is charged when the enrolment becomes active.
- `grading_service`: record grades, amend them with a reason, and build the
  report card.
- `tuition_service`: charge fees.
- `portal_service`: the student and guardian portal, described below.

## Profiles (`academica/profiles.py`)

| Profile | Gets |
|---|---|
| School Secretary | students, guardians, enrolments and their actions; reads the structure, fees, grades and attendance |
| Academic Director | the academic structure, classes, teaching assignments and tuition rules; reads students, enrolments, grades and attendance |
| Teacher | assessments, grades and attendance; reads the classes and their students |
| Student, Guardian | the portal only (`PORTAL`: `view_own_enrolment`, `view_own_grade`, `view_own_studentattendance`, `view_own_tuitioncharge`) |
| Admin | everything of the module except the portal |

## Student / guardian portal

Menu: Education → My school life (route `view_own_enrolment`, page
`front/src/pages/academica/portal/MySchoolPage.vue`). All endpoints are
read-only `GET` actions:

| Endpoint | Permission | Answers |
|---|---|---|
| `enrolments/mine/` | `view_own_enrolment` | the caller's enrolments, each with `relationship` (`self` or the guardian's relationship) |
| `grades/mine/?enrolment=&period=` | `view_own_grade` | the scale, the year's periods, the report card (per subject: weighted average and pass) and every grade |
| `studentattendances/mine/?enrolment=` | `view_own_studentattendance` | totals per status and the latest 200 records |
| `tuitioncharges/mine/?enrolment=` | `view_own_tuitioncharge` | the fees with total, paid and balance (`sales.get_sale_snapshots`), and the balance owed |

**"Own" is never chosen by the client.** It is resolved from the signed-in
user's Person (`Person.user`): the user is either that Student's Person or the
Person of one of the Student's guardians. The lookup is limited to the
request's Entity and Branch.

- An enrolment outside that set answers `404`, as if it did not exist. This
  covers another student, another Entity, and a malformed id. A missing
  `enrolment` is `400`.
- The portal permissions open none of the school's lists or reports:
  `enrolments/`, `grades/`, `students/` and `enrolments/{id}/report/` stay
  `403`.

To give someone access, the user must be linked to the Person of the student
or of the guardian, and hold the Student or Guardian profile at the branch.

New action permissions are created by `manage.py resaas_sync`. Run it before
`migrate`, which applies the profiles through post_migrate `group_creator`.

## Record pages (`view_<model>`)

Every academica model's "view" (the schema's `routes.view`, opened from a list
row) is a record page with the layout of the employee's profile: a header with
the record, its status, Pdf and Edit, then tabs.

- **Details:** the model's own fields, read-only.
- **Related records:** the records of related models that point at it, e.g.
  a student's guardians and enrolments, or an enrolment's grades, attendance
  and fees. Each shows only with `list_<model>`; a new one is created already
  attached to the record.
- **A record's own GET action:** e.g. the enrolment and grade history.

A student's Personal tab is the same person panel as the employee's
(`PersonProfilePanel`).

Frontend:

- shared, in dev/front: `src/components/record/RecordViewPage.vue`,
  `RelatedTable.vue`, `ActionRows.vue`;
- for academica: tabs per model in `front/src/pages/academica/views.js`, routes in
  `routes.js`, page `RecordViewPage.vue`, spec `views.spec.js`.

The related tabs use the generic `?<field>=<id>` filter of BaseAPIView. No
backend change was needed.

## Timetables, documents, transfers, year-end (2026-11-14)

| Feature | API | Permission |
|---|---|---|
| Timetable slot (class, subject, teacher, weekday, start/end, room by id) | `timetableslots/` CRUD | `*_timetableslot` |
| A class's / teacher's / room's week | `GET timetableslots/week/?class_group=&teacher=&room=&academic_year=` | `list_timetableslot` |
| The portal: the student's class week | `GET timetableslots/mine/?enrolment=` | `view_own_enrolment` |
| Report card PDF | `GET enrolments/{id}/report_pdf/?period=` | `view_enrolment` |
| Grade sheet (pauta) PDF | `GET classgroups/{id}/sheet_pdf/?period=` | `view_classgroup` |
| Transcript PDF (every year + prior schooling) | `GET students/{id}/transcript_pdf/` | `view_student` |
| Transfer out | `POST enrolments/{id}/transfer/ {destination, reason?}` | `transfer_enrolment` |
| Prior schooling (transfer in) | `priorschoolings/` CRUD | `*_priorschooling` |
| Year-end preview | `GET academicyears/{id}/progression/?next_year=` | `close_year_academicyear` |
| Close the year | `POST academicyears/{id}/close_year/ {next_year?}` | `close_year_academicyear` |

Rules:

- **Timetable** (`timetable_service.clashes`):
  - a class, a teacher or a room is never in two overlapping slots on the
    same weekday of a year (400);
  - the year is the class's;
  - the room belongs to `laboratorio`: it is kept by id and name, and
    academica imports nothing of it.
- **Documents** (`documents_service`, templates `academica/pdf/`):
  - A4, with the school's colour and logo (django_resaas `qr_card_service`);
  - every text is translated.
- **Transfer out** (`transfer_service`):
  - the enrolment becomes `transferred`, with the destination in its history;
  - the student becomes `transferred` once no enrolment holds a place;
  - event `academica.enrolment.transferred`.
- **Year-end** (`progression_service`):
  - **Result:** every active enrolment gets `result`. It is passed when every
    subject with grades is at or above the scale's pass value, not passed
    otherwise. The enrolment is then completed.
  - **Next year:** a pending enrolment in the next grade level (passed) or the
    same one (not passed).
  - **Graduation:** passing the last grade level graduates the student (event
    `academica.student.graduated`).
  - **Blocking:** an active enrolment without grades blocks the closing (409
    `undecided_enrolments`) until it is completed or cancelled by hand.
  - **Once and atomic:** one transaction, the year is closed, and a second
    close is 409.
  - **Events:** `academica.year.closed`.
- **Profiles:**
  - Academic Director: timetables, closing the year;
  - School Secretary: prior schooling, reads timetables;
  - Teacher: reads timetables.
- **Front:**
  - `modules/academica/timetable/TimetablePage.vue`: a class's week above
    the slots' list;
  - the Prior schooling list;
  - the menu: Timetable, Prior schooling.

Migration `academica.0002`:

- `Enrolment.result` (blank on existing rows);
- the new tables `academica_timetableslot` and `academica_priorschooling`.

## Tests

- `academica/tests/test_enrolment.py`: registration, enrolments, transitions and
  isolation.
- `test_academic.py`: grades, attendance and tuition.
- `test_portal.py`:
  - a student sees only their own records, and a guardian only their students';
  - another student or another Entity answers 404;
  - the portal opens no lists;
  - without the permission, the portal answers 403;
  - the fees show what is owed.

## Known gaps

- Student numbers use the registration year, not the academic year.
- Still to build: dedicated grade and attendance screens, and wiring the `school.enrolment` form.
