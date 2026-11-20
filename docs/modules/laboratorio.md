# The `laboratorio` module

Rooms, laboratories and practical sessions in ReSaaS Ensino (2026-11-18;
see `docs/progress/ensino-modular.md`).

**Dependencies:**

- `academica`: classes and enrolments;
- `pedagogica`: assignments, used as exercises;
- `hr`: teachers are `Employee`s.

None of them imports `laboratorio`. academica's timetable keeps a room by
id and name (`TimetableSlot.room_id` / `room_name`).

## Models

| Model | What |
|---|---|
| Room | classroom / laboratory / workshop of the branch, capacity, location (name unique per branch) |
| Network | range (CIDR), VLAN, gateway of a room |
| Workstation | a computer of a room: code (unique per branch), hostname, IP, MAC, OS, status available / maintenance / retired; `product_id` = the catalogued item (optional); `labmanager_ref` |
| Equipment | other equipment of a room, with status and optional `product_id` |
| Environment | a work environment (software, container image) for sessions |
| LabSession | a class in a room with a teacher and subject: `planned → running → ended`, `planned → cancelled` (server-side only) |
| SeatAssignment | a student (enrolment) at a workstation of a session |
| SessionExercise | a pedagogica assignment distributed in a session |
| RemoteAccessSession | a teacher's remote access to a seated student's workstation (read-only; the audit trail) |

## Rules (backend)

**Sessions:**

- a room holds one planned / running session at a time; an overlap is a 409;
- only a planned session can be edited;
- the moves are `POST labsessions/{id}/start|end|cancel/`; each is an
  AuditLog row (`LAB_SESSION_<STATUS>`) and the event
  `laboratorio.session.<status>`;
- ending a session ends its open remote accesses.

**Seats:**

- the student must be of the session's class;
- the workstation must be in the session's room and available;
- one workstation per student, one student per workstation (constraints:
  a duplicate is a 409).

**Exercises:** only assignments of the session's class.

**Remote access** (`services/remote_access_service.py`):

- `POST labsessions/{id}/remote_access/ {seat, reason, minutes?}`:
  - only while the session is running (otherwise 409);
  - only by the session's own teacher, the signed-in user's Employee
    (otherwise 403);
  - a reason of at least 5 characters;
  - 1 to 60 minutes (default 15), never past the session's end;
  - one active access per seat (constraint).
- It ends by `POST remoteaccesses/{id}/end/`, by the session ending, or by
  expiry. Expiry is checked whenever accesses are read.
- AuditLog: `LAB_REMOTE_ACCESS_STARTED` (with the reason, workstation,
  enrolment, expiry, provider) / `_ENDED` / `_EXPIRED`.
- Event: `laboratorio.remote_access.started`.
- **The student sees it:** `labsessions/mine/` carries the active access on
  their seat.

## Remote access to physical workstations (adapter)

The Lab Manager project was not found on the server, so nothing invents
its API.

- `integrations/labmanager.py` defines the `LabManagerAdapter` contract:
  `start_remote_access`, `end_remote_access`, `workstation_status`.
- The default is `NullLabManagerAdapter`: the access is authorised and
  audited, nothing is opened remotely.
- A real client is plugged in with `LABMANAGER_ADAPTER = "<module>.<Class>"`
  (settings).
- When the adapter raises, the API answers 502 and **no access is recorded**.

## API (PROTECTED)

| Route | Permission |
|---|---|
| CRUD `rooms/`, `networks/`, `workstations/`, `equipment/`, `environments/`, `labsessions/`, `seatassignments/`, `sessionexercises/` | `*_<model>` |
| `POST labsessions/{id}/start/`, `end/`, `cancel/` | `start_` / `end_` / `cancel_labsession` |
| `GET labsessions/{id}/seats/` (with the active access per seat) | `list_seatassignment` |
| `POST labsessions/{id}/remote_access/` | `start_remoteaccesssession` |
| `GET remoteaccesses/` (create 405), `POST remoteaccesses/{id}/end/` | `list_` / `end_remoteaccesssession` |
| `GET labsessions/mine/?enrolment=<own>` (the portal) | `view_own_labsession` |

## Profiles (`laboratorio/profiles.py`)

| Profile | Gets |
|---|---|
| Lab Technician (new) | CRUD of rooms / networks / workstations / equipment / environments; reads sessions and accesses |
| Teacher | reads the places; CRUD of sessions, seats, exercises; moves; opens / ends remote access |
| Academic Director | reads everything; may end a remote access |
| Student, Guardian | `view_own_labsession` |
| Admin | the union of the above |

## Frontend (`front/src/pages/laboratorio`)

- `sessions/LabSessionsPage.vue` (`list_labsession`):
  - the sessions;
  - "New lab session" dialog;
  - start / end / cancel (confirmed with `sDialog`);
  - the seat grid, with a red border while a remote access is open;
  - "Seat a student" dialog;
  - exercises (distribute an assignment of the class);
  - "Open remote access" dialog (reason and minutes). It opens the Lab
    Manager url when there is one; otherwise it says the access was recorded.
- `portal/MyLabSessionsPage.vue` (`view_own_labsession`):
  - the student's workstation and exercises;
  - a red banner while a remote access is open on their workstation.
- Schema-driven lists (`LaboratorioCrudPage.vue`) for rooms, workstations,
  equipment, networks, environments and the remote-access audit trail.

## Tests

`laboratorio/tests/test_labs.py`:

- session moves and the one-session-per-room rule;
- seat rules;
- remote access: not running, wrong teacher, reason and duration checks,
  one per seat, audit, the student's view, end, expiry, the session's end
  closing it, create 405;
- a Lab Manager failure records nothing;
- exercises of the class and the portal boundaries;
- another Entity's room refused.

## Virtual labs (the former Lab Manager, 2026-11-18)

The `lab-manager/` project (a Bash CLI, `lab.sh` v2.2, with its own SQLite)
now lives in this module.

**Before it was deleted:**

- its data was imported into Machava / Sede: 2 labs, 14 machines, 34
  history rows. The history became AuditLog `LAB_LEGACY_*` rows; no
  password was imported;
- the folder was backed up to `/root/backups/lab-manager-2026-11-18.tar.gz`;
- its image (Dockerfile, entrypoint, branding) moved to
  `laboratorio/docker/ubuntu/`.

### Models

- **`VirtualLab`:**
  - `name` is unique on the host; it names the Docker network
    `labmgr-<name>` and the containers `<name>-<user>`;
  - network mode: shared, or isolated (one network per machine);
  - optional class, subject and environment (the default image).
- **`VirtualMachine`:**
  - one per student and lab;
  - stores the container, image, RAM / CPUs, the SSH / HTTP ports Docker
    assigned, the status (running / stopped / missing / deleted), the
    volume `labmgr-<container>-home` and the network;
  - **no password:** it is shown once, at creation or when renewed.

### Services and configuration

- `services/docker_client.py` runs the docker CLI: an argument list, never
  a shell, with a time limit.
- `services/machine_service.py` keeps lab.sh's rules:
  - labels `lab.manager=true`, `lab.name`, `lab.student`, plus
    `lab.entity`;
  - deleting a machine keeps its volume; a volume another container uses is
    never purged;
  - cleanups are dry runs first and only touch labelled objects; there is
    no global prune.
- Configuration is `settings.LABORATORIO`, from `.env` (the former
  `lab.conf`):
  - `LAB_DEFAULT_IMAGE`, `LAB_RAM`, `LAB_CPUS`, `LAB_PUBLIC_HOST`,
    `LAB_BACKUP_DIR`;
  - `LAB_HTTPS_ENABLED` (off: nothing in the image serves 443, so it is not
    published), among others.
- `tasks.create_lab_machines` (Celery): machines for every student of the
  lab's class.

### The command: `manage.py lab`

It replaces `lab.sh` (help in `management/commands/lab.py`):

- `doctor`, `status`, `paths`, `sync`, `history`;
- `lab list` / `create` / `network-mode`;
- `image list` / `build`;
- `network list` / `info` / `prune [--apply]`;
- `machine list` / `info` / `stats` / `create` / `create-group` / start /
  stop / restart (one machine or a group) / `shell` / `password` /
  `delete [--purge-volume] [--cleanup] [--dry-run] [--yes]`;
- `backup` / `backup-all` / `backups` / `restore`;
- `storage audit` / `cleanup [--apply --purge-orphans]`;
- `import-legacy`.

### API

**Staff:**

- CRUD `virtuallabs/`; creating a lab makes its network.
- Lab actions: `network_mode`, `create_machines` (202, in the background),
  `start_machines` / `stop_machines` / `restart_machines`, `sync`, `stats`.
- `virtualmachines/`:
  - POST makes and starts a machine and answers its password once;
  - DELETE removes the container and keeps the volume;
  - actions `start` / `stop` / `restart`, `renew_password`, `backup`.

**Portal:**

- `virtualmachines/mine/?enrolment=`: how to connect, never a password;
- `virtualmachines/{id}/renew_own_password/`: the student's own machine
  only; the new password is shown once.

**Permissions:**

- `network_mode_` / `create_machines_` / `power_` / `sync_virtuallab`;
- `power_` / `renew_password_` / `backup_` / `view_own_` /
  `renew_own_password_virtualmachine`.

**Profiles:**

- Lab Technician: everything;
- Teacher: reads, powers, renews passwords;
- Student: their own machine and password;
- Guardian: view only.

### Front

- `virtual/VirtualLabsPage.vue` (`list_virtuallab`);
- `virtual/MyVirtualMachinesPage.vue` (`view_own_virtualmachine`);
- `virtual/PasswordOnceDialog.vue`.

### State in dev (2026-11-18)

- At the owner's request, every lab container was deleted (12 registered
  plus the unregistered `linux-antonia`).
- The 14 home volumes and the `labmgr-*` networks are kept.
- The imported machines are not yet linked to enrolments (the old
  usernames are not student numbers).

### Tests

`tests/test_virtual.py`, on a fake Docker; with `test_labs.py`,
11 passed.
