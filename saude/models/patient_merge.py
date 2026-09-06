from django.db import models

from django_resaas.engine.core.base.models import BaseModel


class PatientMerge(BaseModel):
    """
    Regista uma fusão de identidade (duas Person que afinal são a
    mesma pessoa) - nunca apaga a Person fundida, só a marca
    `state='Inactive'` e preserva este registo para auditoria/
    reversão manual. entity/branch (via BaseModel) são os da Entity
    que iniciou a fusão (dona do Paciente sobrevivente).

    Fase 5 (ver docs/architecture/patient-longitudinal-health-pharmacy.md)
    - última fase por ser parcialmente irreversível. Único ponto de
    escrita: PatientMergeService.merge() - nunca criar directamente.
    """

    survivor_person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='+',
    )

    merged_person = models.ForeignKey(
        'django_resaas.Person',
        on_delete=models.CASCADE,
        related_name='+',
    )

    performed_by = models.ForeignKey(
        'django_resaas.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    reason = models.TextField(blank=True, null=True)

    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Patient Merge"
        verbose_name_plural = "Patient Merges"

    class RESAAS:

        label_field = "survivor_person.full_name"

        search_fields = [
            "survivor_person__full_name",
            "merged_person__full_name",
        ]

        crud = True

    def __str__(self):
        return f"{self.merged_person_id} -> {self.survivor_person_id}"
