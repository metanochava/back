from django.db import models


class TerminationType(models.TextChoices):
    VOLUNTARY = "voluntary", "Voluntary"
    INVOLUNTARY = "involuntary", "Involuntary"
    RETIREMENT = "retirement", "Retirement"
    END_OF_CONTRACT = "end_of_contract", "End of Contract"
