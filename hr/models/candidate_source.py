from django.db import models


class CandidateSource(models.TextChoices):
    WEBSITE = "website", "Website"
    REFERRAL = "referral", "Referral"
    AGENCY = "agency", "Agency"
    SOCIAL_MEDIA = "social_media", "Social Media"
    OTHER = "other", "Other"
