from django.db import models


class ResignationStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    ACCEPTED = "accepted", "Accepted"
    WITHDRAWN = "withdrawn", "Withdrawn"
