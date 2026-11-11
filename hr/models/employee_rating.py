from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from django_resaas.saas.core.base.models import BaseModel


class EmployeeRatingCommentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class EmployeeRating(BaseModel):
    """A rating (1-5 stars, optional comment) given to an employee.

    Generic (HR): any employee may be rated. The module that owns the
    service rated records where it came from in `source_type`/`source_id`
    (e.g. "saude.agenda" + the appointment id) - one rating per source, so a
    repeated call never counts twice. hr never imports that module.

    The stars count at once; the comment is shown only after someone of the
    Entity approves it (comment_status). Averages: this Entity only, or the
    same Person across every Entity whose employee row shares its ratings
    (Employee.share_ratings_globally) - see employee_rating_service.
    """

    employee = models.ForeignKey("hr.Employee", on_delete=models.CASCADE, related_name="ratings")

    # who rated (the patient's Person, for saude); never shown publicly
    rated_by = models.ForeignKey(
        "django_resaas.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="employee_ratings_given"
    )

    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(null=True, blank=True)

    comment_status = models.CharField(
        max_length=20, choices=EmployeeRatingCommentStatus.choices, default=EmployeeRatingCommentStatus.PENDING
    )
    moderated_at = models.DateTimeField(null=True, blank=True, editable=False)
    moderated_by = models.ForeignKey(
        "django_resaas.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="employee_ratings_moderated", editable=False,
    )

    source_type = models.CharField(max_length=60, editable=False)
    source_id = models.UUIDField(editable=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["source_type", "source_id"], name="hr_employee_rating_one_per_source"),
            models.CheckConstraint(condition=models.Q(stars__gte=1, stars__lte=5), name="hr_employee_rating_stars_1_5"),
        ]

    class RESAAS:
        label_field = "employee__person__full_name"
        search_fields = ["employee__person__full_name", "comment"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.stars}"
