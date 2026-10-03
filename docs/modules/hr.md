# The `hr` module

`hr` is this application's HR / payroll module (`back/hr`), built on
`django_resaas`'s primitives. Its models use the same `BaseModel` / tenant
conventions (see [django_resaas: Public API reference](https://github.com/metanochava/django_resaas/blob/main/docs/api/public-api-reference.md)).

It used to ship inside `django_resaas` (`django_resaas.hr`). It is now a
module of this application, and the framework knows nothing about it:

- `INSTALLED_APPS` / `MY_APPS`: `'hr'` (the app label stays `hr`, so tables,
  ContentTypes, permissions and `'hr.Employee'` references are unchanged);
- activated for every new EntityType through `RESAAS_DEFAULT_MODULES = ["hr"]`
  in `saas/settings.py`;
- its API is `/api/hr/<resource>/`: every view is `@registerView(..., module="hr")`,
  routed by the framework's `build_saas_urls()`;
- its own dashboard permissions (`view_hr_dashboard`, ...) are created in
  `hr/apps.py` with the framework's `ensure_module_permissions`, and it adds
  its permissions to the platform's administration profiles in `hr/profiles.py`;
- tests: `hr/tests` (pytest, `pytest` from `back/`, with the framework's
  `django_resaas.testing` fixtures - see `conftest.py`).

Other modules of this application depend on it (e.g. `saude.Medico.employee`).

## Models (`hr/models/__init__.py`)

-   `Employee`, `Department`, `JobPosition` - core organizational structure. `Employee` links to
    `Person` (from `django_resaas`), an optional `manager` (self-referential), and a `position`.
-   `Specialty`, `EmployeeSpecialty` - skills/specialties an employee can hold.
-   `Shift`, `EmployeeShift`, `ShiftSchedule`, `Attendance` - work-schedule and clock-in/out
    tracking. `Attendance` stores `check_in`/`check_out`, `source` (Manual/Web/Mobile/Biometric/
    RFID/API/External Device - only Manual/Web are actually produced today, the rest exist so the
    field never needs a migration when a real integration shows up), `late_minutes`,
    `early_departure_minutes`, `overtime_minutes`, `worked_minutes` and a `status` (`present`/
    `absent`/`late`).
-   `Holiday` - Entity-wide (`is_entity_wide=True`, the default) or Branch-scoped, and either a
    fixed date (`is_recurring=False`) or a recurring one matched by month/day across years
    (`is_recurring=True`, e.g. Christmas). Queried via `hr/services/holiday_service.is_holiday(entity, branch, date)`.
-   `JobGrade` - level/seniority independent of `JobPosition` (Junior/Senior/... ordered by
    `level`), assignable to an `Employee`.
-   `Contract` - employment contract (dates, type, status). Its `salary` is a reference value,
    not the payroll source of truth. It is gated by its own field permissions
    (`view_contract_salary` / `change_contract_salary`): `view_contract` alone does not reveal it.
    See [django_resaas: Field-level permissions](https://github.com/metanochava/django_resaas/blob/main/docs/security/field-permissions.md).
-   `SalaryComponent`, `EmployeeSalary` - configurable pay components per employee.
-   `PayrollPeriod`, `Payroll`, `PayrollItem`, `Payslip` - payroll runs and their line items.
-   `Promotion`, `Transfer` - immutable history rows for a merit-based position/grade change or a
    Branch/Department/Position move. Created exclusively through `EmployeeAPIView.apply_promotion`/
    `apply_transfer` (`hr/views/employee.py`), which apply the change to
    `Employee.position`/`job_grade`/`branch` in the same transaction - a plain `POST` to
    `promotions/`/`transfers/` is blocked (405). `Employee.position`/`job_grade` are similarly
    blocked from a generic `PATCH` on `employees/{id}/` once created - only these two actions may
    change them. `Transfer` never crosses `Entity` - `to_branch`/`to_department`/`to_position` are
    all validated against the employee's own `entity_id` first.
-   `DisciplinaryCase`, `DisciplinaryAction` - sensitive records (own `view_disciplinarycase`/
    `view_disciplinaryaction` permissions, never assumed from `view_employee`; never surfaced
    through `EmployeeSerializer`). `DisciplinaryCase.status` is a state machine
    (`open` → `under_review` → `resolved`/`dismissed`) driven by `start_review`/`resolve`/`dismiss`
    `@resaas_action`s; creating a case and adding an action are plain CRUD `POST`s.
-   `Resignation` - plain CRUD create (`status=submitted`), only `accept`/`withdraw` are actions;
    `accept` is what actually moves `Employee.employment_status` to `resigned`.
-   `Termination` - immutable, created exclusively through `EmployeeAPIView.terminate_employee`,
    which also sets `Employee.employment_status=terminated`/`termination_date` in the same
    transaction.
-   `EmployeeOffboarding`, `EmployeeOffboardingTask` - same checklist/progress shape as
    `EmployeeOnboarding` (Fase 5), but with a **fixed** universal task list
    (`lifecycle_service.DEFAULT_OFFBOARDING_TASKS`) instead of a per-Entity template model - exit
    tasks (return assets, close accounts, final payroll, clearance, exit interview) have no real
    per-Entity customization need yet, so a template here would be a model with no consumer.
    Created exclusively through `EmployeeAPIView.start_offboarding`.
-   `LeaveType` - per-Entity (Annual/Sick/Maternity/...), `is_paid` (drives whether a balance is
    checked at all - see below), `requires_approval`, optional `default_days_per_year`.
-   `LeaveRequest` - `employee`, `leave_type`, `start_date`/`end_date`, a server-computed `days`,
    and a `status` state machine (`draft` → `pending` → `approved`/`rejected`/`cancelled`; an
    already-`approved` request can still move to `cancelled`, which reverses its ledger entry -
    every other terminal state has no outgoing transition). `status`/`days`/`approved_by`/
    `approved_at`/`rejection_reason` are `read_only` on `LeaveRequestSerializer` - they only ever
    change through the `submit`/`approve`/`reject`/`cancel` `@resaas_action`s below, never a plain
    `PATCH`.
-   `LeaveBalanceEntry` - a ledger (allocation/usage/adjustment/expiry rows), not a decremented
    counter - an employee's balance for a `LeaveType` is always `sum(amount)` over their entries
    (`leave_service.current_balance()`). `usage`/`expiry` entries can only be created by the
    workflow below (`LeaveBalanceEntrySerializer` rejects them from a direct POST); `allocation`/
    `adjustment` are legitimately manual (e.g. HR granting the yearly days).

    No separate `LeavePolicy` model: `LeaveType.default_days_per_year` is enough for what Fase 3
    actually needs (submit/approve against a balance) - accrual/expiry/minimum-notice rules are a
    real future need, but a model with no consumer yet would just be dead weight (see the
    project's own "não construir 50 models vazios" rule). Split it out once a phase actually reads
    those extra rules.

### `hr/services/leave_service.py`

-   `calculate_business_days(entity, branch, start_date, end_date)` - counts days in the range
    that are neither a weekend (Sat/Sun, hardcoded - a real per-Entity weekend-days setting is a
    plausible future need, but nothing today reads one) nor a holiday
    (`holiday_service.is_holiday()`, Fase 2).
-   `submit(leave_request, *, actor)` - `draft` → `pending`. Validates `end_date >= start_date`,
    rejects overlap with the employee's own other `pending`/`approved` requests, computes `days`,
    and - only when `leave_type.is_paid` - rejects the request if `days` exceeds
    `current_balance()`. Emits `hr.leave.requested`.
-   `approve(leave_request, *, actor)` - `pending` → `approved`. Refuses if `actor` is the same
    person as `leave_request.employee` (self-approval - matched via `Employee.person.user_id`,
    the only real link this project has between `Employee` and `User`; an employee with no linked
    login can never trigger this check). Creates a `usage` `LeaveBalanceEntry` for `-days` (paid
    types only). Emits `hr.leave.approved`.
-   `reject(leave_request, *, actor, reason)` - `pending` → `rejected`; `reason` is required.
    Emits `hr.leave.rejected`.
-   `cancel(leave_request, *, actor)` - `draft`/`pending`/`approved` → `cancelled`; if it was
    `approved`, creates an `adjustment` entry for `+days` reversing the usage. Emits
    `hr.leave.cancelled`.
-   Every transition is validated against `LeaveRequest.ALLOWED_TRANSITIONS`
    (`hr/models/leave_request.py`) - e.g. `rejected` → `approved` always raises `LeaveError`,
    regardless of caller.

## Business logic

### `hr/services/attendance_service.py`

-   `calculate_attendance(attendance)` - looks up the `ShiftSchedule` for the attendance's
    employee/date; if none exists, just saves the instance as-is (see the fixed bug below) and
    returns. Otherwise: marks the attendance `absent` if there's no `check_in`; if `check_in` is
    after the shift's `start_time` (shift bounds computed by `_shift_bounds()`, which accounts for
    shifts crossing midnight - `end_time <= start_time` means the shift ends the next day, e.g.
    23:00-07:00), computes `late_minutes` and marks it `late`; if `check_out` is set, computes
    `worked_minutes`, and either `overtime_minutes` (checked out after the shift ended) or
    `early_departure_minutes` (checked out before it ended) - never both. Saves the instance.
-   `check_in(employee, *, source=AttendanceSource.MANUAL, actor=None)` /
    `check_out(employee, *, actor=None)` - get-or-create (check-in) or fetch (check-out) today's
    `Attendance` row for the employee, stamp `timezone.now()`, call `calculate_attendance()`, and
    emit `hr.attendance.checked_in` / `hr.attendance.checked_out` (plus
    `hr.attendance.overtime_recorded` when `overtime_minutes > 0`) via `EventDispatcher.emit()` -
    `hr`'s first real use of the event system. Both raise `AttendanceError` (not `NameError`
    anymore - see below) for: a second check-in the same day while one is already open, a
    check-out with no open check-in, or a second check-out. The `check_in`/`check_out`
    `@resaas_action`s on `EmployeeAPIView` (`hr/views/employee.py`) wrap these in
    `transaction.atomic()` and turn `AttendanceError` into an HTTP 400.

    **Fixed (Fase 2):** this module used to reference `ShiftSchedule`/`Attendance` without
    importing either name - both were undefined, so calling `check_in()`/`check_out()`/
    `calculate_attendance()` raised `NameError`. Also fixed as part of the same change: the
    no-`ShiftSchedule` branch of `calculate_attendance()` used to `return` before ever calling
    `.save()`, so a `check_in`/`check_out` stamped for an employee with no shift scheduled was
    silently never persisted. All datetimes go through `django.utils.timezone`
    (`timezone.now()`/`timezone.localdate()`/`timezone.make_aware()`), not the naive
    `datetime.now()` the original code used - this project runs with `USE_TZ=True`, so a naive
    value compared against one read back from the DB (timezone-aware) raises `TypeError`.

### `hr/services/payroll_service.py`

-   `calculate_salary(employee, base_salary, overtime_rate=1.5, late_penalty=0.5)` - sums
    `overtime_minutes` and `late_minutes` across all of the employee's `attendances`, computes
    `overtime_pay = total_overtime * overtime_rate` and `late_discount = total_late *
    late_penalty`, and returns `final_salary = base_salary + overtime_pay - late_discount` along
    with the intermediate figures (`base_salary`, `overtime_minutes`, `late_minutes`,
    `overtime_pay`, `late_discount`, `final_salary`) as a dict. Note the units mismatch: overtime
    and late minutes are multiplied directly by a rate/penalty with no explicit conversion to
    hours or a currency-per-minute basis - callers should treat `overtime_rate`/`late_penalty` as
    already being "per minute" figures, not "per hour" ones.

### `hr/services/lifecycle_service.py`

Fase 9 (Employee Lifecycle) - same service+exception shape as every previous phase (`LifecycleError`
raised on any business-rule violation, `transaction.atomic()` left to the caller,
`EventDispatcher.emit()` for every meaningful transition).

-   `apply_promotion(employee, *, new_position, new_job_grade=None, effective_date, reason="",
    approved_by=None, actor=None)` - creates the `Promotion` row and applies `new_position`/
    `new_job_grade` to the `Employee` in the same call. Emits `hr.employee.promoted`.
-   `apply_transfer(employee, *, to_branch, to_department=None, to_position=None, effective_date,
    reason="", approved_by=None, actor=None)` - validates `to_branch`/`to_department`/
    `to_position` all belong to `employee.entity_id` (raises `LifecycleError` otherwise, before
    touching anything), then creates the `Transfer` row and applies `to_branch`/`to_position` to
    the `Employee`. Emits `hr.employee.transferred`.
-   `start_review(case)` / `resolve_case(case)` / `dismiss_case(case)` - `DisciplinaryCase.status`
    transitions, validated against `DisciplinaryCase.ALLOWED_TRANSITIONS`.
-   `case_opened(case, *, actor=None)` / `issue_disciplinary_action(case, action, *, actor=None)` -
    called from `DisciplinaryCaseAPIView.perform_create`/`DisciplinaryActionAPIView.perform_create`
    right after the plain-CRUD row is saved; emit `hr.disciplinary.case_opened`/
    `hr.disciplinary.action_issued`.
-   `accept_resignation(resignation, *, actor=None)` - `submitted` → `accepted`; raises if the
    employee's employment has already ended; sets `Employee.employment_status=resigned` and
    `termination_date=resignation.last_working_date`. Emits `hr.employee.resigned`.
-   `withdraw_resignation(resignation, *, actor=None)` - `submitted` → `withdrawn`; touches nothing
    on `Employee`.
-   `terminate_employee(employee, *, termination_type, termination_date, reason="",
    initiated_by=None, actor=None)` - raises `LifecycleError` if the employee's employment has
    already ended (idempotency guard - can't terminate twice); otherwise creates the `Termination`
    row and sets `Employee.employment_status=terminated`/`termination_date`. Emits
    `hr.employee.terminated`.
-   `start_offboarding(employee, *, actor=None)` - raises if an `in_progress` offboarding already
    exists for this employee; otherwise creates `EmployeeOffboarding` + seeds
    `DEFAULT_OFFBOARDING_TASKS` as `EmployeeOffboardingTask` rows. Emits `hr.offboarding.started`.
-   `complete_offboarding_task`/`reopen_offboarding_task`/`offboarding_progress`/
    `complete_offboarding`/`cancel_offboarding` - identical shape to their `onboarding_service.py`
    counterparts (Fase 5): `complete_offboarding` raises if any `is_required` task is still
    pending, and emits `hr.offboarding.completed`.

## Management commands

### `hr_create_missing_users`

Gives every Employee whose Person has no User its User account. The core
creates a User only when a Person is **created**
(`django_resaas.saas.core.services.person_user_service`); Employees whose
Person existed before that have none. This is the explicit backfill for them.

```bash
python manage.py hr_create_missing_users                  # dry run: lists who would get one
python manage.py hr_create_missing_users --apply          # creates them
python manage.py hr_create_missing_users --entity <id>    # only one Entity
```

- Uses the core's `create_user_for_person`: username from the first name,
  a temporary password the user must replace, the User's state copied from
  the Person (an **Inactive** Person gets an **Inactive** User).
- Idempotent: only Persons without a User are touched; soft-deleted
  Employees are left alone; a Person employed in several Entities gets one User.
- Each Employee is its own transaction: a failure is reported (`FAILED`) and
  the others still proceed.
- It grants **no access**: what the new User may do still depends on its
  groups (`BranchUserGroup`), like any account.
- Tests: `hr/tests/test_create_missing_users_command.py`.
