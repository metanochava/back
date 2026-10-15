from django.db import models


class TrainingSessionMode(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    ONLINE = "online", "Online"
