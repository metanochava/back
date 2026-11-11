from django.db import models


def active_state_field():
    """TimeModel.state for a patient document (any saude model that reaches
    the Paciente): Active from creation. Guarded by
    saude/tests/test_patient_documents_active.py.

    TimeModel's default ('Inactive') left new consultations, prescriptions,
    ... out of the right-menu history, which lists only Active documents
    (HistoryList: state=Active) - however they were created (the page's form,
    a view action, a service). 'Inactive' means nothing for these documents:
    cancelling goes through the document edit policy, removing through the
    soft delete."""
    return models.CharField(
        default="Active",
        choices=(("Inactive", "Inactive"), ("Active", "Active")),
    )
