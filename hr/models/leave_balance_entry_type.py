from django.db import models


class LeaveBalanceEntryType(models.TextChoices):
    ALLOCATION = "allocation", "Allocation"
    USAGE = "usage", "Usage"
    ADJUSTMENT = "adjustment", "Adjustment"
    EXPIRY = "expiry", "Expiry"
