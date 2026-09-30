from django.db import models
from django.core.exceptions import ValidationError

from django_resaas.saas.core.base.models import BaseModel


class EmploymentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PROBATION = "probation", "Probation"
    SUSPENDED = "suspended", "Suspended"
    TERMINATED = "terminated", "Terminated"
    RESIGNED = "resigned", "Resigned"
    RETIRED = "retired", "Retired"


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Full Time"
    PART_TIME = "part_time", "Part Time"
    CONTRACTOR = "contractor", "Contractor"
    INTERN = "intern", "Intern"


# An employee's manager chain is only ever a handful of levels deep in
# practice; this bounds the cycle walk in clean() so corrupted data
# (e.g. imported directly, bypassing clean()) can never spin forever.
MAX_MANAGER_CHAIN_DEPTH = 50


class Employee(BaseModel):

    # ==========================================
    # RELATIONSHIPS
    # ==========================================

    person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='employees'
    )

    manager = models.ForeignKey(
        'hr.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='subordinates'
    )

    position = models.ForeignKey(
        'hr.JobPosition',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees'
    )

    job_grade = models.ForeignKey(
        'hr.JobGrade',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees'
    )

    # ==========================================
    # CORE FIELDS
    # ==========================================

    # Unique per Entity (see Meta.unique_together below), not globally -
    # two different Entities may legitimately reuse the same scheme
    # (e.g. both starting at EMP-2026-000001). blank=True so
    # EmployeeAPIView.perform_create can auto-generate it via
    # EmployeeNumberService when the caller doesn't supply one; existing
    # rows already carry a value from before this field allowed blanks.
    code = models.CharField(
        max_length=50,
        blank=True,
        db_index=True
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
        null=True,
        blank=True,
    )

    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        null=True,
        blank=True,
    )

    work_email = models.EmailField(null=True, blank=True)
    work_phone = models.CharField(max_length=30, null=True, blank=True)

    # ==========================================
    # DATES
    # ==========================================

    hire_date = models.DateField()

    termination_date = models.DateField(
        null=True,
        blank=True
    )

    # ==========================================
    # VALIDATIONS
    # ==========================================

    def clean(self):

        super().clean()

        if self.manager and self.manager == self:

            raise ValidationError({
                "manager": "An employee cannot be their own manager."
            })

        if self.manager_id:

            current = self.manager
            depth = 0

            while current is not None:

                depth += 1

                if depth > MAX_MANAGER_CHAIN_DEPTH:
                    raise ValidationError({
                        "manager": "Manager chain is too deep - "
                        "possible corrupted data."
                    })

                if self.pk is not None and current.pk == self.pk:
                    raise ValidationError({
                        "manager": "This assignment would create a "
                        "management cycle (this employee already "
                        "manages, directly or indirectly, the chosen "
                        "manager)."
                    })

                current = current.manager

        if (
            self.hire_date and
            self.termination_date and
            self.termination_date < self.hire_date
        ):

            raise ValidationError({
                "termination_date":
                "The termination date cannot be earlier than the hire date."
            })

    # ==========================================
    # HELPERS
    # ==========================================

    @property
    def is_active(self):

        return self.termination_date is None

    # ==========================================
    # META
    # ==========================================

    class Meta:

        unique_together = (
            ('person', 'branch'),
            ('entity', 'code'),
        )

        indexes = [

            models.Index(fields=['code']),

            models.Index(fields=['hire_date']),

            models.Index(fields=['position']),

            models.Index(fields=['manager']),

            models.Index(fields=['person']),

        ]

    # ==========================================
    # RESAAS
    # ==========================================

    class RESAAS:

        label_field = "code"

        # relation pickers show an Employee as a card (see
        # core/utils/relation_preview.py)
        preview = {
            "title": "person__full_name",
            "subtitle": ["code", "work_email"],
            "avatar": "person__photo",
            "meta": ["position__title"],
        }

        search_fields = [

            "code",

            "person__name",

            "person__surname",

            "person__full_name"

        ]

        crud = True

        routes = {

            'list': "list_employee",

            'view': "view_employee",

            'add': "add_employee",

            'change': "change_employee"

        }

    # ==========================================
    # STRING REPRESENTATION
    # ==========================================

    def __str__(self):

        position = (
            self.position
            if self.position
            else "Sem Cargo"
        )

        return f"{self.person.full_name} ({position})"