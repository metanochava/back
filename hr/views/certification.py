# hr/views/certification.py

from django_resaas.saas.core.base.views import BaseAPIView, registerView

from hr.models.certification import Certification
from hr.serializers.certification import CertificationSerializer


@registerView('certifications', module='hr')
class CertificationAPIView(BaseAPIView):
    queryset = Certification.objects.all()
    serializer_class = CertificationSerializer

    # Certification is plain CRUD (pedido secção 55: no service for a
    # bare create) - but issuing one is still a real domain event
    # (pedido secção 56's list explicitly names
    # hr.training.certification_issued), so it's emitted here rather than
    # skipped just because there's no training_service function to hang it
    # off of.
    def perform_create(self, serializer):
        from django_resaas.saas.core.events import EventDispatcher

        # BaseAPIView.perform_create() is the one that stamps
        # entity_id/branch_id/created_by/updated_by onto the save() call -
        # reused as-is, not reimplemented, so this override only adds the
        # event emission on top.
        super().perform_create(serializer)
        instance = serializer.instance

        EventDispatcher.emit(
            "hr.training.certification_issued",
            instance=instance,
            actor=self.request.user,
            context={
                "employee_id": str(instance.employee_id),
                "certification_id": str(instance.id),
            },
        )
