from django.db import models


class OnboardingTaskCategory(models.TextChoices):
    """Inspired by pedido secção 31's example list, not copied literally -
    trimmed to categories that actually earn their own bucket."""
    DOCUMENTS = "documents", "Documents"
    ACCOUNT = "account", "Account"
    EQUIPMENT = "equipment", "Equipment"
    ORIENTATION = "orientation", "Orientation"
    DEPARTMENT = "department", "Department Induction"
    OTHER = "other", "Other"
