from django.db import models
from django_resaas.engine.core.base.models import BaseModel


class PatientIdentifier(BaseModel):
    """
    Identificador externo de um Paciente (documento de identidade,
    número de seguro, número de registo legado, ...) - NÃO o `nid`
    interno gerado automaticamente em Paciente.create() (esse já é
    globalmente único e não precisa de matching).

    Fase 1 da iniciativa Patient longitudinal (ver
    docs/architecture/patient-longitudinal-health-pharmacy.md):
    permite que PatientMatchingService encontre o mesmo Paciente
    através de Entities diferentes sem alterar o modelo Paciente
    existente. Não cria nem funde Paciente automaticamente.
    """

    paciente = models.ForeignKey(
        'saude.Paciente',
        on_delete=models.CASCADE,
        related_name='identifiers'
    )

    identifier_type = models.CharField(
        max_length=50
    )

    identifier = models.CharField(
        max_length=100
    )

    issuer = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    is_primary = models.BooleanField(
        default=False
    )

    valid_from = models.DateField(
        blank=True,
        null=True
    )

    valid_until = models.DateField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Patient Identifier"
        verbose_name_plural = "Patient Identifiers"

        indexes = [
            models.Index(fields=["identifier_type", "identifier"]),
        ]

    class RESAAS:

        label_field = "identifier"

        search_fields = [
            "identifier",
            "identifier_type",
            "paciente__nid",
        ]

        crud = True

        routes = {
            "list": "list_patientidentifier",
            "view": "view_patientidentifier",
            "add": "add_patientidentifier",
            "change": "change_patientidentifier"
        }

    def __str__(self):

        return f"{self.identifier_type}:{self.identifier} ({self.paciente_id})"
