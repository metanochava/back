from django.db import models
from django_resaas.saas.core.base.models import BaseModel


class DadoVital(BaseModel):

    # =====================================================
    # RELAÇÕES
    # =====================================================

    paciente = models.ForeignKey(
        "saude.Paciente",
        on_delete=models.CASCADE,
        related_name="dados_vitais"
    )

    consulta = models.ForeignKey(
        "saude.Consulta",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dados_vitais"
    )

    # the visit (appointment) the record was taken for - links it exactly
    # instead of "same patient, after the check-in"
    agenda = models.ForeignKey(
        "saude.Agenda",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dados_vitais"
    )

    # set by the server: the professional signed in (never sent by the client)
    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.CASCADE,
        related_name="dados_vitais_registados"
    )

    # =====================================================
    # IDENTIFICAÇÃO DO REGISTO
    # =====================================================

    tipo = models.CharField(
        max_length=20,
        choices=[
            ("triagem", "Triage"),
            ("consulta", "Consultation"),
            ("internamento", "Inpatient"),
            ("urgencia", "Emergency"),
        ],
        default="consulta"
    )

    # =====================================================
    # ANTROPOMETRIA
    # =====================================================

    peso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Peso (Kg)"
    )

    altura = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Altura (m)"
    )

    circunferencia_abdominal = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    # =====================================================
    # SINAIS VITAIS
    # =====================================================

    temperatura = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )

    # where the temperature was taken (the normal range depends on it)
    temperatura_local = models.CharField(
        max_length=12,
        choices=[
            ("axilar", "Axillary"),
            ("oral", "Oral"),
            ("timpanica", "Tympanic"),
            ("retal", "Rectal"),
        ],
        null=True,
        blank=True
    )

    frequencia_cardiaca = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="bpm"
    )

    frequencia_respiratoria = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="irpm"
    )

    pulso = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    saturacao_oxigenio = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="%"
    )

    ta_sistolica = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    ta_diastolica = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    glicemia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    # the glucose value is read against the moment it was measured
    glicemia_momento = models.CharField(
        max_length=12,
        choices=[
            ("jejum", "Fasting"),
            ("pos_prandial", "Postprandial"),
            ("aleatoria", "Random"),
        ],
        null=True,
        blank=True
    )

    # =====================================================
    # AVALIAÇÃO CLÍNICA
    # =====================================================

    dor = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Escala de 0 a 10"
    )

    estado_consciencia = models.CharField(
        max_length=20,
        choices=[
            ("alerta", "Alert"),
            ("sonolento", "Drowsy"),
            ("confuso", "Confused"),
            ("inconsciente", "Unconscious"),
        ],
        null=True,
        blank=True
    )

    glasgow = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    # =====================================================
    # INTERNAMENTO
    # =====================================================

    is_internment = models.BooleanField(
        default=False
    )

    observacao = models.TextField(
        null=True,
        blank=True
    )

    # =====================================================
    # DATA
    # =====================================================

    data = models.DateField(
        auto_now_add=True
    )

    hora = models.TimeField(
        auto_now_add=True
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        verbose_name = "Dado Vital"
        verbose_name_plural = "Dados Vitais"
        ordering = [
            "-data",
            "-hora"
        ]

    class RESAAS:

        label_field = "paciente.person.full_name"

        search_fields = [
            "paciente__person__name",
            "paciente__person__surname",
            "paciente__person__full_name",
            "paciente__nid",
            "employee__person__full_name",
            "tipo"
        ]

        crud = True

        routes = {
            "list": "list_dadovital",
            "view": "view_dadovital",
            "add": "add_dadovital",
            "change": "change_dadovital"
        }

    # =====================================================
    # PROPRIEDADES
    # =====================================================

    @property
    def imc(self):

        if not self.peso or not self.altura:
            return None

        return round(
            float(self.peso) /
            (float(self.altura) ** 2),
            2
        )

    @property
    def classificacao_imc(self):

        if self.imc is None:
            return None

        if self.imc < 18.5:
            return "Baixo peso"

        if self.imc < 25:
            return "Peso normal"

        if self.imc < 30:
            return "Sobrepeso"

        if self.imc < 35:
            return "Obesidade Grau I"

        if self.imc < 40:
            return "Obesidade Grau II"

        return "Obesidade Grau III"

    @property
    def peso_ideal(self):

        if not self.altura:
            return None

        return round(
            22 * (float(self.altura) ** 2),
            2
        )

    @property
    def pressao_arterial(self):

        if self.ta_sistolica and self.ta_diastolica:
            return f"{self.ta_sistolica}/{self.ta_diastolica}"

        return None

    # =====================================================
    # STRING
    # =====================================================

    def __str__(self):

        return (
            f"{self.paciente.person.full_name}"
            f" - {self.data}"
        )