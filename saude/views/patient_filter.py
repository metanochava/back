"""?patient=<id> on the clinical document lists: one patient's documents -
the right-menu history of the patient's pages (HistoryList) asks for it.
A document reaches its patient through its consultation, so the plain
`?field=value` filter of BaseAPIView (direct fields only) cannot do it.
Applied on the tenant-scoped queryset; an id that is not a uuid, or not a
patient of this scope, just matches nothing."""
import uuid


class PatientFilterMixin:
    # the path from the document to its Paciente
    patient_lookup = "consulta__paciente"

    def get_queryset(self):
        queryset = super().get_queryset()
        patient_id = self.request.query_params.get("patient")
        if not patient_id:
            return queryset
        try:
            uuid.UUID(str(patient_id))
        except ValueError:
            return queryset.none()
        return queryset.filter(**{f"{self.patient_lookup}_id": patient_id})
