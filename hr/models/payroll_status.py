from django.db import models


class PayrollStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CALCULATED = "calculated", "Calculated"
    REVIEWED = "reviewed", "Reviewed"
    CONFIRMED = "confirmed", "Confirmed"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
