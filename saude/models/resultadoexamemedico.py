import mimetypes
import os

from django.db import models

from django_resaas.engine.core.base.models import BaseModel
from django_resaas.engine.core.utils import upload_path


class ResultadoExameMedico(BaseModel):

    FOLDER = "Folder"
    FILE = "File"

    TIPO_CHOICES = (
        (FOLDER, "Pasta"),
        (FILE, "Ficheiro"),
    )

    paciente = models.ForeignKey(
        "saude.Paciente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="arquivos_medicos"
    )

    pai = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="filhos"
    )

    nome = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=FOLDER
    )

    ordem = models.PositiveIntegerField(
        default=0
    )

    item_pedido = models.ForeignKey(
        "saude.ItemPedidoExameMedico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resultados"
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
        max_length=500,
        null=True,
        blank=True
    )

    tamanho = models.BigIntegerField(
        default=0
    )

    mime_type = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    extensao = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    favorito = models.BooleanField(
        default=False
    )

    na_lixeira = models.BooleanField(
        default=False
    )

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
            "-tipo",
            "nome",
        ]

        indexes = [

            models.Index(
                fields=[
                    "paciente",
                    "pai",
                ]
            ),

            models.Index(
                fields=[
                    "tipo",
                ]
            ),

            models.Index(
                fields=[
                    "nome",
                ]
            ),

            models.Index(
                fields=[
                    "favorito",
                ]
            ),

            models.Index(
                fields=[
                    "na_lixeira",
                ]
            ),

        ]

    class RESAAS:

        label_field = "nome"

        search_fields = [

            "nome",

            "paciente__person__full_name",

            "item_pedido__exame__nome",

            "valor_resultado",

            "laudo",

        ]

        crud = True

        routes = {

            "list": "list_resultadoexamemedico",

            "view": "view_resultadoexamemedico",

            "add": "add_resultadoexamemedico",

            "change": "change_resultadoexamemedico",

        }

    @property
    def is_folder(self):
        return self.tipo == self.FOLDER

    @property
    def is_file(self):
        return self.tipo == self.FILE

    @property
    def children_count(self):
        return self.filhos.filter(
            na_lixeira=False
        ).count()

    @property
    def has_children(self):
        return self.children_count > 0

    @property
    def filename(self):
        if not self.file:
            return None

        return os.path.basename(
            self.file.name
        )

    @property
    def extension(self):
        return self.extensao or ""

    @property
    def icon(self):

        if self.is_folder:
            return "folder"

        if self.extensao == ".pdf":
            return "picture_as_pdf"

        if self.extensao in [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".webp",
        ]:
            return "image"

        if self.extensao in [
            ".doc",
            ".docx",
        ]:
            return "description"

        if self.extensao in [
            ".xls",
            ".xlsx",
        ]:
            return "table_view"

        if self.extensao in [
            ".zip",
            ".rar",
            ".7z",
        ]:
            return "folder_zip"

        return "insert_drive_file"

    @classmethod
    def explorer(
        cls,
        paciente,
        entity,
        branch,
    ):
        return cls.objects.filter(
            paciente=paciente,
            entity=entity,
            branch=branch,
            na_lixeira=False,
        )

    def save(self, *args, **kwargs):

        if self.file:

            if not self.nome:

                self.nome = os.path.basename(
                    self.file.name
                )

            self.tamanho = self.file.size

            self.extensao = (
                os.path.splitext(
                    self.file.name
                )[1]
                .lower()
            )

            self.mime_type = (
                mimetypes.guess_type(
                    self.file.name
                )[0]
                or ""
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome or "Sem nome"