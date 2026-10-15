from django.db import models


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Full Time"
    PART_TIME = "part_time", "Part Time"
    CONTRACTOR = "contractor", "Contractor"
    INTERN = "intern", "Intern"
