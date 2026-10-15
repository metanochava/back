from django.db import models


class EmployeeTrainingStatus(models.TextChoices):
    ENROLLED = "enrolled", "Enrolled"
    ATTENDING = "attending", "Attending"
    COMPLETED = "completed", "Completed"
    DROPPED = "dropped", "Dropped"
    FAILED = "failed", "Failed"
