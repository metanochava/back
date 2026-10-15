from django.db import models


class JobOpeningStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    ON_HOLD = "on_hold", "On Hold"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"
