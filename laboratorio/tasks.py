"""Long laboratorio operations (Celery: saas/celery.py autodiscovers this)."""
from celery import shared_task


@shared_task(name="laboratorio.create_lab_machines")
def create_lab_machines(lab_id, user_id, image=None, ram=None, cpus=None):
    """A machine for every student of the lab's class (create-group). The
    passwords are not kept: the teacher renews them per machine when needed."""
    from django_resaas.saas.models.user import User
    from laboratorio.models import VirtualLab
    from laboratorio.services import machine_service

    lab = VirtualLab.objects.get(id=lab_id)
    user = User.objects.filter(id=user_id).first()
    result = machine_service.create_for_class(lab=lab, user=user, image=image, ram=ram, cpus=cpus)
    return {"created": [{k: v for k, v in row.items() if k != "password"} for row in result["created"]],
            "failed": result["failed"]}
