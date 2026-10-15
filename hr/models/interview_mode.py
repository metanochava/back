from django.db import models


class InterviewMode(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    VIDEO = "video", "Video"
    PHONE = "phone", "Phone"
