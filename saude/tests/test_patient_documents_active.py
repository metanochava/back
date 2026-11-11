"""Every patient document is Active from creation: the right-menu history
(HistoryList) and other lists ask for state=Active, and TimeModel's default
('Inactive') made new consultations, prescriptions, ... disappear from them.
A saude model that reaches the Paciente through its relations must declare
`state = active_state_field()` (saude/models/clinical_document_state.py)."""
from django.apps import apps
from django.test import SimpleTestCase

from django_resaas.saas.core.base.models import BaseModel

# the patient itself: Inactive there means "merged into another" (patient_merge_service)
NOT_DOCUMENTS = {"Paciente", "PatientMerge"}


def _reaches_patient(model, seen=()):
    for field in model._meta.fields:
        related = field.related_model if field.is_relation else None
        if related is None or related._meta.app_label != "saude":
            continue
        if related.__name__ == "Paciente":
            return True
        if related.__name__ not in seen and related is not model and _reaches_patient(related, seen + (model.__name__,)):
            return True
    return False


class PatientDocumentsAreActiveTests(SimpleTestCase):

    def test_every_patient_document_is_created_active(self):
        inactive = [
            model.__name__
            for model in apps.get_app_config("saude").get_models()
            if issubclass(model, BaseModel)
            and model.__name__ not in NOT_DOCUMENTS
            and _reaches_patient(model)
            and model._meta.get_field("state").default != "Active"
        ]
        self.assertEqual(inactive, [], "declare state = active_state_field() on these models")
