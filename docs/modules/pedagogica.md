# The `pedagogica` module

Teaching and learning in ReSaaS Ensino (2026-11-14 to 2026-11-18; see
`docs/progress/ensino-modular.md`).

**Dependencies:**

- **`academica`:** classes, subjects, periods, enrolments, assessments and
  grades, through its models and public services (`portal_service`,
  `grading_service`). `academica` never imports `pedagogica`.
- **`hr`:** teachers are `Employee`s; the signed-in teacher is the Employee
  whose Person is the user (`assignment_service.teacher_of`).

## Models

| Model | What |
|---|---|
| LessonPlan | objectives, content, activities and resources of a class / subject, draft or ready |
| Lesson | the **digital board**, described below |
| LessonAttachment | an image, document or drawing used by a lesson's blocks (core file storage, `upload_path`) |
| Material | a file or a link of a subject (a class, or every class of the grade level); published or not |
| Assignment | instructions, due date, maximum score; draft → published → closed; optionally an academica `assessment` |
| Submission | a student's answer (text and / or a file), **once per enrolment**; `submitted` / `late` / `graded` with a score and feedback |
| CalendarEvent | test, homework, activity, meeting or holiday of a class (or of the whole school) |
| ProgressNote | a teacher's observation / positive / concern on an enrolment; `shared` with the student and guardians or not |
| ClassMessage | a teacher's message to a class |

**The digital board (`Lesson`):**

- ordered `blocks`: `text` (rich text), `image`, `document`, `diagram`
  (text), `drawing` (a PNG of the whiteboard);
- a class, a subject, a date and a teacher;
- `search_text` (the blocks' text, without tags) makes the history
  searchable;
- published, the class's students consult it.

## API (PROTECTED, BaseAPIView)

| Route | Permission |
|---|---|
| CRUD of every model (`lessonplans/`, `lessons/`, `lessonattachments/`, `materials/`, `assignments/`, `calendarevents/`, `progressnotes/`, `classmessages/`) | `*_<model>` |
| `POST lessons/{id}/publish/`, `unpublish/` | `publish_lesson`, `unpublish_lesson` |
| `GET lessons/search/?q=&class_group=&subject=` (newest first; every word of `q`) | `list_lesson` |
| `POST assignments/{id}/publish/`, `close/` | `publish_assignment`, `close_assignment` |
| `GET assignments/{id}/submissions/`; `submissions/` (read-only list) | `list_submission` |
| `POST submissions/{id}/grade/ {score, feedback?}` | `grade_submission` |

**Grading:**

- the score is between 0 and the assignment's maximum;
- when the assignment names an academica assessment, the grade goes there,
  converted to the scale. It is recorded once; a regrade amends it with the
  reason "Assignment regraded";
- event `pedagogica.submission.graded`.

## The portal (students and guardians)

`GET <resource>/mine/?enrolment=<own>`. Only an enrolment of the caller is
accepted (academica `portal_service.own_enrolment`): another one is 404, and
the lists themselves are 403.

| Route | Permission | Gives |
|---|---|---|
| `lessons/mine/?subject=&q=` | `view_own_lesson` | the class's **published** lessons with their attachments |
| `materials/mine/` | `view_own_material` | published materials of the class, or of every class of its grade level |
| `assignments/mine/` | `view_own_assignment` | the class's published / closed assignments, each with the student's submission |
| `POST assignments/{id}/submit/ {enrolment, text?, file?}` | `submit_assignment` | once; `late` after the due date; 409 when not open; 404 for another class |
| `calendarevents/mine/` | `view_own_calendarevent` | the class's and the school's events |
| `progressnotes/mine/` | `view_own_progressnote` | the **shared** notes only |
| `classmessages/mine/` | `view_own_classmessage` | the class's published messages |

## Profiles (`pedagogica/profiles.py`)

The names are academica's.

| Profile | Gets |
|---|---|
| Teacher | everything of the module; grades submissions; publishes |
| Academic Director | reads everything; manages the calendar |
| Student | the portal and `submit_assignment` |
| Guardian | the portal |
| Admin | everything except the portal |

The action permissions are created on migrate
(`signals.grant_pedagogica_action_permissions`).

## Frontend (`front/src/pages/pedagogica`)

- **Digital board** (`board/DigitalBoardPage.vue`, route `list_lesson`):
  - the searchable history (class, subject, words);
  - the editor in blocks: rich text, image / document upload, a text
    diagram, and drawing on `board/WhiteboardCanvas.vue` (pen colours,
    widths, eraser, undo, clear; pointer: mouse, touch or pen);
  - save, publish / unpublish.
- **My lessons** (`portal/MyLessonsPage.vue`, route `view_own_lesson`): the
  student's lessons by date, by subject and searchable.
- **Safe text:** the lesson's HTML is cleaned by `utils/sanitizeHtml.js`
  (an allowlist; no scripts, handlers, styles or `javascript:` links) before
  it is shown.
- **The rest:** schema-driven lists (`PedagogicaCrudPage.vue`) for plans,
  materials, assignments, submissions, the calendar, progress notes and
  class messages.

## Tests

- `pedagogica/tests/test_pedagogy.py`:
  - lessons searchable, only published ones reaching the class;
  - submission once, late, graded into the assessment with the 0-20
    conversion and the regrade amendment;
  - another class's assignment refused;
  - materials, calendar, shared notes and messages of the class;
  - the portal never opens the lists nor another student's enrolment;
  - another Entity's class refused.
- Front: `utils/sanitizeHtml.spec.js`.
