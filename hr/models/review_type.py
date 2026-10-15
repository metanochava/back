from django.db import models


class ReviewType(models.TextChoices):
    """pedido secção 34: at least Self/Manager/HR now, room to add
    PEER/SUBORDINATE later (a full 360) without a destructive migration -
    TextChoices is additive by nature, no schema change needed to grow
    this list."""
    SELF = "self", "Self Review"
    MANAGER = "manager", "Manager Review"
    HR = "hr", "HR Review"
