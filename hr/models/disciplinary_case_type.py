from django.db import models


class DisciplinaryCaseType(models.TextChoices):
    MISCONDUCT = "misconduct", "Misconduct"
    ATTENDANCE = "attendance", "Attendance"
    PERFORMANCE = "performance", "Performance"
    POLICY_VIOLATION = "policy_violation", "Policy Violation"
    OTHER = "other", "Other"
