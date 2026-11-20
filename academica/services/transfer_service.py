"""A student leaving for another institution (transfer out) and the
schooling a student brings from one (PriorSchooling, a transfer in).

The enrolment is never deleted: its status becomes "transferred" with the
destination in its history (enrolment_service.change_status). The student
becomes "transferred" when no enrolment of theirs holds a place any more.
"""
from django.db import transaction

from django_resaas.saas.core.events import EventDispatcher
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica.models import Enrolment, Student
from academica.services import enrolment_service


@transaction.atomic
def transfer_out(*, request, enrolment, destination, reason=""):
    destination = (destination or "").strip()
    if not destination:
        raise ResaasAPIException("Say which institution the student is going to.", code="invalid",
                                 details={"destination": ["Say which institution the student is going to."]})
    text = f"{destination}: {reason.strip()}" if (reason or "").strip() else destination
    enrolment = enrolment_service.change_status(request=request, enrolment=enrolment,
                                                to_status=Enrolment.STATUS_TRANSFERRED, reason=text)
    student = Student.objects.select_for_update().get(pk=enrolment.student_id)
    if not student.enrolments.filter(status__in=Enrolment.HOLDING).exists():
        student.status = Student.STATUS_TRANSFERRED
        student.updated_by = request.user
        student.save(update_fields=["status", "updated_by", "updated_at"])
    EventDispatcher.emit("academica.enrolment.transferred", instance=enrolment, actor=request.user,
                         context={"enrolment_id": str(enrolment.id), "student_id": str(student.id),
                                  "destination": destination})
    return enrolment
