from django.db import models
from django_resaas.saas.core.base.models import BaseModel
from saude.models.clinical_document_state import active_state_field


class DoencaCorrente(BaseModel):

    # a patient document: Active from creation (saude/models/clinical_document_state.py)
    state = active_state_field()

    nome = models.CharField(
        max_length=200
    )

    paciente = models.ForeignKey(
        'saude.Paciente',
        on_delete=models.CASCADE,
        related_name='doencas_correntes'
    )

    class Meta:
        verbose_name = "Doença Corrente"
        verbose_name_plural = "Doenças Correntes"

        unique_together = (
            "paciente",
            "nome"
        )

    class RESAAS:

        label_field = "nome"

        search_fields = [
            "nome",
            "paciente__person__full_name",
            "paciente__nid"
        ]

        crud = True

        routes = {
            'list': "list_doencacorrente",
            'view': "view_doencacorrente",
            'add': "add_doencacorrente",
            'change': "change_doencacorrente"
        }

    def __str__(self):

        return (
            f"{self.nome} - "
            f"{self.paciente.person.full_name}"
        )