"""Demo data for the Health module: demo patients and a doctor's appointments
around today, with coherent states and patient-flow times, so the Reception /
Nursing / Doctor dashboards and the check-in, check-out and vital-signs flows
can be tried on a fresh database. Used by `manage.py seed_saude_demo`.

Safety (CLAUDE.md §11, §76):
- the Entity is always explicit; a Branch is explicit when the Entity has
  more than one - nothing is picked as "the first";
- only records this seed created are ever touched: demo patients by their
  NID prefix, demo appointments by DEMO_TAG in `observacao`;
- idempotent: patients are reused, days that already have demo appointments
  are skipped (unless reset);
- the doctor is an existing user's Person; a missing Employee record in the
  Branch is created for it. No user or password is ever created.
"""
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from django_resaas.hr.models.employee import Employee
from django_resaas.saas.models.branch import Branch
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.models.person import Person
from django_resaas.saas.models.user import User
from saude.models.agenda import Agenda
from saude.models.paciente import Paciente

DEMO_TAG = "[demo-seed]"
# appointments created by hand before this command existed (same purpose)
LEGACY_TAGS = ("[seed] test data for Dr. Cassia",)
NID_PREFIX = "DEMO-"

SLOTS = [time(h, m) for h in range(8, 17) for m in (0, 30)]  # 08:00 .. 16:30
REASONS = [
    "Consulta de rotina", "Febre há 3 dias", "Dor de cabeça", "Controlo da tensão arterial",
    "Tosse persistente", "Dor abdominal", "Seguimento de análises", "Diabetes - controlo",
    "Dor lombar", "Renovação de receita", "Check-up anual", "Tonturas",
]
FIRST_NAMES = [
    ("Ana", "F"), ("Beatriz", "F"), ("Carla", "F"), ("Dércia", "F"), ("Elsa", "F"), ("Fátima", "F"),
    ("Graça", "F"), ("Helena", "F"), ("Isabel", "F"), ("Joana", "F"), ("Luísa", "F"), ("Marta", "F"),
    ("Alberto", "M"), ("Bento", "M"), ("Carlos", "M"), ("Daniel", "M"), ("Ernesto", "M"), ("Filipe", "M"),
    ("Gilberto", "M"), ("Hélio", "M"), ("Inácio", "M"), ("João", "M"), ("Lucas", "M"), ("Mário", "M"),
]
SURNAMES = ["Sitoe", "Macuácua", "Nhaca", "Mabunda", "Cumaio", "Zandamela", "Matsinhe", "Tembe",
            "Massingue", "Chavana", "Bila", "Mondlane", "Cossa", "Langa", "Muianga", "Nhantumbo"]


class SeedError(Exception):
    """A missing/ambiguous input - reported to the operator, nothing written."""


@dataclass
class SeedReport:
    entity: str = ""
    branch: str = ""
    doctor: str = ""
    doctor_employee_created: bool = False
    patients_created: int = 0
    patients_total: int = 0
    removed: int = 0
    days: dict = field(default_factory=dict)   # date -> {estado: count} | "skipped"

    @property
    def created(self):
        return sum(sum(v.values()) for v in self.days.values() if isinstance(v, dict))


# ------------------------------------------------------------------ inputs

def _by_name_or_id(queryset, value, what):
    matches = list(queryset.filter(Q(name__iexact=value) | Q(id=value) if _looks_like_id(value) else Q(name__iexact=value))[:2])
    if not matches:
        raise SeedError(f"{what} '{value}' not found.")
    if len(matches) > 1:
        raise SeedError(f"More than one {what} is called '{value}': use its id.")
    return matches[0]


def _looks_like_id(value):
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def resolve_entity(value):
    if not value:
        raise SeedError("--entity is required (name or id).")
    return _by_name_or_id(Entity.objects.all(), value, "Entity")


def resolve_branch(entity, value=None):
    branches = Branch.objects.filter(entity=entity)
    if value:
        return _by_name_or_id(branches, value, "Branch")
    only = list(branches[:2])
    if len(only) == 1:
        return only[0]
    raise SeedError("The Entity has no Branch." if not only else
                    "The Entity has several Branches: choose one with --branch.")


def resolve_doctor(entity, branch, username, *, dry_run=False):
    """(Employee, created) for the user's Person in this Branch."""
    if not username:
        raise SeedError("--doctor-user is required (username or email of the doctor).")
    user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
    if user is None:
        raise SeedError(f"User '{username}' not found.")
    person = Person.objects.filter(user=user).first()
    if person is None:
        raise SeedError(f"User '{username}' has no Person record.")

    employee = Employee.objects.filter(person=person, entity=entity, branch=branch).first()
    if employee:
        return employee, False
    if dry_run:
        return Employee(person=person, entity=entity, branch=branch), True
    employee = Employee.objects.create(
        person=person, entity=entity, branch=branch, code=f"DEMO-DOC-{str(person.id)[:8]}",
        hire_date=timezone.localdate(), created_by=user, updated_by=user, state="Active",
    )
    return employee, True


# ------------------------------------------------------------------ data

def ensure_patients(entity, branch, count, actor, rng, *, dry_run=False):
    """At least `count` demo patients in the Branch. Returns (patients, created)."""
    prefix = f"{NID_PREFIX}{str(branch.id)[:8]}-"
    existing = list(Paciente.objects.filter(branch=branch, nid__startswith=prefix).select_related("person").order_by("nid"))
    created = 0
    number = len(existing)

    while len(existing) < count:
        number += 1
        first, gender = FIRST_NAMES[(number - 1) % len(FIRST_NAMES)]
        surname = SURNAMES[rng.randrange(len(SURNAMES))]
        born = date(rng.randint(1950, 2015), rng.randint(1, 12), rng.randint(1, 28))
        if dry_run:
            existing.append(Paciente(nid=f"{prefix}{number:03d}", person=Person(name=first, surname=surname)))
        else:
            person = Person.objects.create(name=first, surname=surname, gender=gender, date_of_birth=born)
            existing.append(Paciente.objects.create(
                nid=f"{prefix}{number:03d}", person=person, entity=entity, branch=branch,
                created_by=actor, updated_by=actor, state="Active",
            ))
        created += 1

    return existing, created


def _demo_appointments(doctor):
    tags = Q(observacao=DEMO_TAG)
    for legacy in LEGACY_TAGS:
        tags |= Q(observacao=legacy)
    return Agenda.objects.filter(tags, medico=doctor)


def _state(offset, index_today, rng):
    if offset < 0:
        return rng.choices(["concluida", "faltou", "cancelada"], weights=[70, 15, 15])[0]
    if offset > 0:
        return rng.choice(["marcada", "marcada", "confirmada"])
    # today: done, waiting (nursing queue), in progress, and several to check in
    plan = ["concluida", "concluida", "concluida", "em_espera", "em_espera", "em_atendimento"]
    return plan[index_today] if index_today < len(plan) else rng.choice(["marcada", "confirmada"])


def _flow_times(agenda, offset, rng, now):
    start = timezone.make_aware(datetime.combine(agenda.data, agenda.hora_inicio))
    estado = agenda.estado
    if estado in ("concluida", "em_atendimento", "em_espera"):
        agenda.checked_in_at = (now - timedelta(minutes=rng.randint(8, 45))
                                if offset == 0 and estado != "concluida"
                                else start - timedelta(minutes=rng.randint(0, 15)))
    if estado in ("concluida", "em_atendimento"):
        agenda.service_started_at = (now - timedelta(minutes=rng.randint(2, 7))
                                     if offset == 0 and estado == "em_atendimento"
                                     else agenda.checked_in_at + timedelta(minutes=rng.randint(5, 40)))
    if estado == "concluida":
        agenda.completed_at = agenda.service_started_at + timedelta(minutes=rng.randint(10, 30))


# ------------------------------------------------------------------ run

def run(*, entity, branch=None, doctor_user, patients=12, days_before=2, days_after=3,
        per_day=(9, 12), reset=False, dry_run=False, seed=None, today=None, now=None):
    if days_before < 0 or days_after < 0:
        raise SeedError("--days-before and --days-after must be 0 or more.")
    low, high = per_day
    if not (1 <= low <= high <= len(SLOTS)):
        raise SeedError(f"--per-day must be between 1 and {len(SLOTS)} (min <= max).")

    rng = random.Random(seed)
    today = today or timezone.localdate()
    now = now or timezone.now()

    entity = resolve_entity(entity)
    branch = resolve_branch(entity, branch)
    report = SeedReport(entity=entity.name, branch=branch.name)

    with transaction.atomic():
        doctor, created_doctor = resolve_doctor(entity, branch, doctor_user, dry_run=dry_run)
        report.doctor = doctor.person.full_name or str(doctor.person)
        report.doctor_employee_created = created_doctor
        actor = doctor.person.user

        pool, report.patients_created = ensure_patients(
            entity, branch, max(patients, high), actor, rng, dry_run=dry_run
        )
        report.patients_total = len(pool)

        first_day = today - timedelta(days=days_before)
        last_day = today + timedelta(days=days_after)
        if reset and doctor.pk:
            in_range = _demo_appointments(doctor).filter(data__range=(first_day, last_day))
            report.removed = in_range.count()
            if not dry_run:
                in_range.delete()

        for offset in range(-days_before, days_after + 1):
            day = today + timedelta(days=offset)
            already = doctor.pk and _demo_appointments(doctor).filter(data=day).exists()
            if already and not reset:
                report.days[day] = "skipped"
                continue

            taken = set(
                Agenda.objects.filter(medico=doctor, data=day).exclude(estado="cancelada")
                .values_list("hora_inicio", flat=True)
            ) if doctor.pk else set()
            free = [slot for slot in SLOTS if slot not in taken]
            count = min(len(free), rng.randint(low, high), len(pool))
            slots = sorted(rng.sample(free, count))
            day_patients = rng.sample(pool, count)   # one appointment per patient per day

            counts = {}
            for index, (slot, patient) in enumerate(zip(slots, day_patients)):
                agenda = Agenda(
                    paciente=patient, medico=doctor, data=day, hora_inicio=slot,
                    hora_fim=(datetime.combine(day, slot) + timedelta(minutes=30)).time(),
                    motivo=rng.choice(REASONS), observacao=DEMO_TAG,
                    estado=_state(offset, index, rng),
                    entity=entity, branch=branch, created_by=actor, updated_by=actor, state="Active",
                )
                _flow_times(agenda, offset, rng, now)
                if not dry_run:
                    agenda.save()
                counts[agenda.estado] = counts.get(agenda.estado, 0) + 1
            report.days[day] = counts

        if dry_run:
            transaction.set_rollback(True)

    return report
