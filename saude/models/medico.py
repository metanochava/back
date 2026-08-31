from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path



class Medico(BaseModel):

    employee = models.OneToOneField(
        'hr.Employee',
        on_delete=models.CASCADE,
        related_name='medico'
    )

    numero_ordem = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    especialidade = models.ManyToManyField(
    'hr.Specialty',
        blank=True,
        related_name="medicos"
    )
    categoria = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    assinatura = models.ImageField(
        upload_to=upload_path("assinaturas_medicos"),
        max_length=500,
        null=True,
        blank=True
    )

    carimbo = models.ImageField(
        upload_to=upload_path("carimbos_medicos"),
        max_length=500,
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"

        unique_together = (
            "entity",
            "employee"
        )

    class RESAAS:

        label_field = "employee.person.full_name"

        search_fields = [
            "employee__person__name",
            "employee__person__surname",
            "employee__person__full_name",
            "numero_ordem",
            "especialidade__title"
        ]

        crud = True

        routes = {
            "list": "list_medico",
            "view": "view_medico",
            "add": "add_medico",
            "change": "change_medico"
        }

    def __str__(self):
        return self.employee.person.full_name