from django.db import models
from django_resaas.core.base.models import BaseModel
from django_resaas.core.utils import upload_path


class ResultadoExameMedico(BaseModel):

    paciente = models.ForeignKey('saude.Paciente', on_delete=models.SET_NULL, null=True,  blank=True)
    nome = models.CharField(max_length=500, null=True) 
    pertence = models.CharField(max_length=100, null=True,  blank=True) 
    objecto = models.CharField(max_length=100, null=True,  blank=True) 
 

    item_pedido = models.ForeignKey(
        'saude.ItemPedidoExameMedico',
        null=True,
        on_delete=models.SET_NULL,
        related_name='resultados'
    )


    numero_revisao = models.PositiveIntegerField(
        default=1
    )

    valor_resultado = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    laudo = models.TextField(
        null=True,
        blank=True
    )

    file = models.FileField(
        upload_to=upload_path("resultados_exames"),
        null=True,
        blank=True
    )

    tipochoice = (
        ('Folder', 'Folfer'),
        ('File', 'File')
    )

    tipo = models.CharField(max_length=100, null=True, choices=tipochoice, default=tipochoice[0])


    data_colheita = models.DateTimeField(
        null=True,
        blank=True
    )

    data_resultado = models.DateTimeField(
        null=True,
        blank=True
    )

    emitido_por = models.ForeignKey(
        "django_resaas.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resultados_emitidos"
    )

    validado_por = models.ForeignKey(
        "django_resaas.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resultados_validados"
    )

    validado = models.BooleanField(
        default=False
    )

    data_validacao = models.DateTimeField(
        null=True,
        blank=True
    )

    assinado_digitalmente = models.BooleanField(
        default=False
    )

    hash_documento = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Resultado de Exame Médico"
        verbose_name_plural = "Resultados de Exames Médicos"
        ordering = [
            "-data_resultado",
            "-created_at"
        ]

    class RESAAS:

        label_field = "item_pedido.exame.nome"

        searchable_fields = [
            "item_pedido.exame.nome",
            "item_pedido.pedido.consulta.paciente.person.full_name",
            "valor_resultado",
            "laudo"
        ]

        crud = True

        routes = {
            "list": "add_resultadoexamemedico",
            "view": "view_resultadoexamemedico",
            "add": "add_resultadoexamemedico",
            "change": "change_resultadoexamemedico"
        }

    def __str__(self):

        paciente = getattr(
            self.item_pedido.pedido.consulta.paciente.person,
            "full_name",
            "Paciente"
        )

        exame = self.item_pedido.exame.nome

        return f"{paciente} - {exame}"