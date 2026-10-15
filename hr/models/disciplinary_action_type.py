from django.db import models


class DisciplinaryActionType(models.TextChoices):
    VERBAL_WARNING = "verbal_warning", "Verbal Warning"
    WRITTEN_WARNING = "written_warning", "Written Warning"
    SUSPENSION = "suspension", "Suspension"
    TERMINATION_RECOMMENDATION = "termination_recommendation", "Termination Recommendation"
    OTHER = "other", "Other"
