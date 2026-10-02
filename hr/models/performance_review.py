# hr/models/performance_review.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from django_resaas.saas.core.base.models import BaseModel


class ReviewType(models.TextChoices):
    """pedido secção 34: at least Self/Manager/HR now, room to add
    PEER/SUBORDINATE later (a full 360) without a destructive migration -
    TextChoices is additive by nature, no schema change needed to grow
    this list."""
    SELF = "self", "Self Review"
    MANAGER = "manager", "Manager Review"
    HR = "hr", "HR Review"


class ReviewStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"


# Same explicit-state-machine shape as LeaveRequest/Application/
# EmployeeOnboarding - a review is immutable history once submitted
# (pedido secção 34's spirit + the project's general "preserve history"
# rule already applied to Contract/Payslip/EmployeeOnboardingTask).
ALLOWED_TRANSITIONS = {
    ReviewStatus.DRAFT: {ReviewStatus.SUBMITTED},
    ReviewStatus.SUBMITTED: set(),
}


class PerformanceReview(BaseModel):
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='performance_reviews',
    )

    cycle = models.ForeignKey(
        'hr.PerformanceCycle',
        on_delete=models.CASCADE,
        related_name='reviews',
    )

    review_type = models.CharField(max_length=20, choices=ReviewType.choices)

    # Null for a SELF review where reviewer == employee would be a
    # pointless duplicate FK - the employee being reviewed already IS the
    # reviewer in that case, so this stays null and the service/serializer
    # treat "no reviewer" + review_type == SELF as that case explicitly.
    reviewer = models.ForeignKey(
        'hr.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviews_given',
    )

    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.DRAFT,
    )

    overall_rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'cycle']),
        ]

    class RESAAS:
        label_field = "id"
        search_fields = ["employee__person__full_name", "review_type", "status"]
        crud = True

    def __str__(self):
        return f"{self.employee} - {self.get_review_type_display()} ({self.cycle})"
