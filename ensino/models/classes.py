"""Class groups, students, guardians and enrolments. Identity stays in
django_resaas Person (never copied); teachers are hr.Employee."""
from django.db import models
from django.db.models import Q

from django_resaas.saas.core.base.models import BaseModel


class ClassGroup(BaseModel):
    """A class ("5th A, morning") of an academic year and grade level, in a branch."""

    SHIFT_CHOICES = (("morning", "Morning"), ("afternoon", "Afternoon"), ("evening", "Evening"), ("full_day", "Full day"))

    academic_year = models.ForeignKey("ensino.AcademicYear", on_delete=models.PROTECT, related_name="class_groups")
    grade_level = models.ForeignKey("ensino.GradeLevel", on_delete=models.PROTECT, related_name="class_groups")
    name = models.CharField(max_length=40)
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES, default="morning")
    capacity = models.PositiveSmallIntegerField(default=40)
    homeroom_teacher = models.ForeignKey("hr.Employee", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="homeroom_classes")
    room = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ["academic_year__start_date", "grade_level__order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "academic_year", "name"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_class_name_unique"),
        ]

    class RESAAS:
        label_field = "name"
        search_fields = ["name", "grade_level__name", "academic_year__name"]
        crud = True

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class Student(BaseModel):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_GRADUATED = "graduated"
    STATUS_TRANSFERRED = "transferred"
    STATUS_CHOICES = ((STATUS_ACTIVE, "Active"), (STATUS_INACTIVE, "Inactive"),
                      (STATUS_GRADUATED, "Graduated"), (STATUS_TRANSFERRED, "Transferred"))

    person = models.ForeignKey("django_resaas.Person", on_delete=models.PROTECT, related_name="student_records")
    number = models.CharField(max_length=30, editable=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    admission_date = models.DateField()
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ["person__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "person"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_one_student_per_person"),
            models.UniqueConstraint(fields=["entity", "number"], name="ensino_student_number_unique"),
        ]

    class RESAAS:
        label_field = "person__full_name"
        search_fields = ["person__full_name", "number"]
        crud = True

    def __str__(self):
        return f"{self.number} - {self.person}"


class Guardian(BaseModel):
    RELATIONSHIP_CHOICES = (("mother", "Mother"), ("father", "Father"), ("grandparent", "Grandparent"),
                            ("sibling", "Sibling"), ("uncle_aunt", "Uncle / aunt"), ("legal_guardian", "Legal guardian"),
                            ("other", "Other"))

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardians")
    person = models.ForeignKey("django_resaas.Person", on_delete=models.PROTECT, related_name="guarded_students")
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default="other")
    # who is billed (sales customer) for this student's fees; none -> the student
    pays = models.BooleanField(default=False)
    emergency_contact = models.BooleanField(default=False)
    can_pick_up = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Guardian"
        verbose_name_plural = "Guardians"
        constraints = [
            models.UniqueConstraint(fields=["student", "person"], condition=Q(deleted_at__isnull=True),
                                    name="ensino_guardian_unique"),
            models.UniqueConstraint(fields=["student"], condition=Q(pays=True, deleted_at__isnull=True),
                                    name="ensino_one_paying_guardian"),
        ]

    class RESAAS:
        label_field = "person__full_name"
        search_fields = ["person__full_name", "student__person__full_name"]
        crud = True


class Enrolment(BaseModel):
    """A student in a programme / grade level (and class) for an academic year.
    Its status changes only through enrolment_service (never a PATCH), each
    change recorded in EnrolmentStatusChange."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_TRANSFERRED = "transferred"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = ((STATUS_PENDING, "Pending"), (STATUS_ACTIVE, "Active"), (STATUS_SUSPENDED, "Suspended"),
                      (STATUS_TRANSFERRED, "Transferred"), (STATUS_COMPLETED, "Completed"), (STATUS_CANCELLED, "Cancelled"))
    # the statuses that hold a place (one per student and year; count in the class capacity)
    HOLDING = (STATUS_PENDING, STATUS_ACTIVE, STATUS_SUSPENDED)

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrolments")
    academic_year = models.ForeignKey("ensino.AcademicYear", on_delete=models.PROTECT, related_name="enrolments")
    programme = models.ForeignKey("ensino.Programme", on_delete=models.PROTECT, related_name="enrolments")
    grade_level = models.ForeignKey("ensino.GradeLevel", on_delete=models.PROTECT, related_name="enrolments")
    class_group = models.ForeignKey(ClassGroup, null=True, blank=True, on_delete=models.PROTECT, related_name="enrolments")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, editable=False)
    enrolled_on = models.DateField()

    class Meta:
        verbose_name = "Enrolment"
        verbose_name_plural = "Enrolments"
        ordering = ["-academic_year__start_date", "student__person__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["student", "academic_year"],
                                    condition=Q(status__in=("pending", "active", "suspended"), deleted_at__isnull=True),
                                    name="ensino_one_enrolment_per_year"),
        ]

    class RESAAS:
        label_field = "student__person__full_name"
        search_fields = ["student__person__full_name", "student__number", "class_group__name"]
        crud = True


class EnrolmentStatusChange(BaseModel):
    """Who changed an enrolment's status, when, from what, to what and why."""

    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="status_changes", editable=False)
    from_status = models.CharField(max_length=12, blank=True, default="", editable=False)
    to_status = models.CharField(max_length=12, editable=False)
    reason = models.TextField(blank=True, default="", editable=False)

    class Meta:
        verbose_name = "Enrolment status change"
        verbose_name_plural = "Enrolment status changes"
        ordering = ["created_at"]

    class RESAAS:
        label_field = "to_status"
        search_fields = ["enrolment__student__person__full_name"]
        crud = False
