from django.db import models
from django_resaas.saas.core.base.models import BaseModel

class Paciente(BaseModel):
    STATUS_CHOICES=[
        ("Active","Active"),
        ("Inactive","Inactive"),
        ("Deceased","Deceased")
    ]

    nid=models.CharField(max_length=50)
    person=models.ForeignKey(
        "django_resaas.Person",
        on_delete=models.CASCADE,
        related_name="pacientes"
    )
    status=models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Active"
    )
    religion=models.CharField(
        max_length=150,
        null=True,
        blank=True
    )
    clinical_alert=models.TextField(
        null=True,
        blank=True
    )
    special_needs=models.TextField(
        null=True,
        blank=True
    )
    care_preferences=models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name="Paciente"
        verbose_name_plural="Pacientes"
        constraints=[
            models.UniqueConstraint(
                fields=["person","branch"],
                name="unique_patient_person_branch"
            ),
            models.UniqueConstraint(
                fields=["nid","branch"],
                name="unique_patient_nid_branch"
            )
        ]

    class RESAAS:
        label_field="person.full_name"
        search_fields=[
            "nid",
            "person__name",
            "person__surname",
            "person__full_name",
            "person__email",
            "person__phone"
        ]
        crud=True
        routes={
            "list":"list_paciente",
            "view":"view_paciente",
            "add":"add_paciente",
            "change":"change_paciente"
        }

    @property
    def emergency_contact(self):
        """The person's emergency PersonContact (replaces the legacy
        person_a_contactar/numero_a_contactar columns) - the emergency-
        flagged one if any, otherwise their first contact, or None."""
        contacts = self.person.contacts
        return contacts.filter(is_emergency=True).first() or contacts.first()

    def __str__(self):
        return f"{self.person.full_name} ({self.nid})"