from django.db import models


class EmploymentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PROBATION = "probation", "Probation"
    SUSPENDED = "suspended", "Suspended"
    TERMINATED = "terminated", "Terminated"
    RESIGNED = "resigned", "Resigned"
    RETIRED = "retired", "Retired"
