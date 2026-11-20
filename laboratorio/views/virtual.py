"""Virtual labs and machines (the former Lab Manager), PROTECTED.

Staff:
- CRUD virtuallabs/ (create makes the lab's Docker network); POST
  virtuallabs/{id}/network_mode/ {mode}; POST .../create_machines/ (a machine
  for every student of the lab's class, in the background); POST
  .../start|stop|restart_machines/; POST .../sync/; GET .../stats/.
- virtualmachines/: list / retrieve / change the student; POST {lab,
  enrolment | username, image?, ram?, cpus?} makes and starts a machine and
  answers its password once; DELETE removes the container and keeps the home
  volume (purging is a command-line decision); POST {id}/start|stop|restart/,
  {id}/renew_password/ (the new password once), {id}/backup/.

Students and guardians: GET virtualmachines/mine/?enrolment=<own> (how to
connect, never a password); POST virtualmachines/{id}/renew_own_password/
{enrolment} - the student's own machine only, the new password once.
"""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.exceptions import ResaasAPIException

from academica.services import portal_service
from laboratorio import models as m
from laboratorio import serializers as s
from laboratorio.services import machine_service as ms


@registerView("virtuallabs")
class VirtualLabAPIView(BaseAPIView):
    queryset = m.VirtualLab.objects.select_related("class_group", "subject", "environment")
    serializer_class = s.VirtualLabSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            super().perform_create(serializer)
            ms.ensure_shared_network(serializer.instance)      # a Docker failure rolls the lab back (502)

    def perform_destroy(self, instance):
        if instance.machines.filter(removed_at__isnull=True).exists():
            raise ResaasAPIException("Delete the lab's machines first.", code="lab_has_machines", status_code=409)
        super().perform_destroy(instance)

    @resaas_action(detail=True, methods=["post"], label="Network mode", icon="lan",
                   permission="network_mode_virtuallab")
    def network_mode(self, request, pk=None):
        moved = ms.set_network_mode(lab=self.get_object(), mode=request.data.get("mode"), user=request.user,
                                    request=request)
        return Response({"lab": self.get_serializer(self.get_object()).data, "machines": moved})

    @resaas_action(detail=True, methods=["post"], label="Create the class's machines", icon="dns",
                   permission="create_machines_virtuallab")
    def create_machines(self, request, pk=None):
        """In the background (Celery): the passwords are not shown - each
        student renews their own (virtualmachines/{id}/renew_own_password/)."""
        from laboratorio.tasks import create_lab_machines

        lab = self.get_object()
        if not lab.class_group_id:
            raise ResaasAPIException("The lab has no class.", code="invalid",
                                     details={"class_group": ["The lab has no class."]})
        create_lab_machines.delay(str(lab.id), str(request.user.id), request.data.get("image") or None,
                                  request.data.get("ram") or None, request.data.get("cpus") or None)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)

    def _power(self, request, action):
        return Response(ms.power_lab(lab=self.get_object(), action=action, user=request.user, request=request))

    @resaas_action(detail=True, methods=["post"], label="Start the machines", icon="play_arrow",
                   permission="power_virtuallab")
    def start_machines(self, request, pk=None):
        return self._power(request, "start")

    @resaas_action(detail=True, methods=["post"], label="Stop the machines", icon="stop",
                   permission="power_virtuallab")
    def stop_machines(self, request, pk=None):
        return self._power(request, "stop")

    @resaas_action(detail=True, methods=["post"], label="Restart the machines", icon="restart_alt",
                   permission="power_virtuallab")
    def restart_machines(self, request, pk=None):
        return self._power(request, "restart")

    @resaas_action(detail=True, methods=["post"], label="Synchronise", icon="sync", permission="sync_virtuallab")
    def sync(self, request, pk=None):
        return Response(ms.sync(self.get_object().machines.all()))

    @resaas_action(detail=True, methods=["get"], label="Usage", icon="monitoring", permission="view_virtuallab",
                   visible=False)
    def stats(self, request, pk=None):
        return Response(ms.stats(self.get_object().machines.all()))


@registerView("virtualmachines")
class VirtualMachineAPIView(BaseAPIView):
    queryset = m.VirtualMachine.objects.filter(removed_at__isnull=True).select_related(
        "lab", "enrolment__student__person")
    serializer_class = s.VirtualMachineSerializer

    def create(self, request, *args, **kwargs):
        data = s.VirtualMachineCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        v = data.validated_data
        vm, password = ms.create_machine(lab=v["lab"], user=request.user, enrolment=v.get("enrolment"),
                                         username=v.get("username") or None, image=v.get("image") or None,
                                         ram=v.get("ram") or None, cpus=v.get("cpus") or None, request=request)
        return Response({**self.get_serializer(vm).data, "password": password}, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        ms.delete(vm=instance, user=self.request.user, request=self.request)

    def _power(self, request, action):
        return Response(self.get_serializer(ms.power(vm=self.get_object(), action=action, user=request.user,
                                                     request=request)).data)

    @resaas_action(detail=True, methods=["post"], label="Start", icon="play_arrow", permission="power_virtualmachine")
    def start(self, request, pk=None):
        return self._power(request, "start")

    @resaas_action(detail=True, methods=["post"], label="Stop", icon="stop", permission="power_virtualmachine")
    def stop(self, request, pk=None):
        return self._power(request, "stop")

    @resaas_action(detail=True, methods=["post"], label="Restart", icon="restart_alt",
                   permission="power_virtualmachine")
    def restart(self, request, pk=None):
        return self._power(request, "restart")

    @resaas_action(detail=True, methods=["post"], label="Renew the password", icon="key",
                   permission="renew_password_virtualmachine")
    def renew_password(self, request, pk=None):
        return Response({"password": ms.renew_password(vm=self.get_object(), user=request.user, request=request)})

    @resaas_action(detail=True, methods=["post"], label="Backup", icon="backup", permission="backup_virtualmachine")
    def backup(self, request, pk=None):
        path = ms.backup(vm=self.get_object(), user=request.user, request=request)
        return Response({"file": path.rsplit("/", 1)[-1]}, status=status.HTTP_201_CREATED)

    def _own(self, request, enrolment_id):
        enrolment = portal_service.own_enrolment(request, enrolment_id)
        return enrolment, m.VirtualMachine.objects.filter(entity_id=enrolment.entity_id, enrolment=enrolment,
                                                          removed_at__isnull=True).select_related("lab")

    @resaas_action(detail=False, methods=["get"], url_path="mine", label="My virtual machines", icon="dns",
                   permission="view_own_virtualmachine", visible=False)
    def view_own(self, request):
        _, machines = self._own(request, request.query_params.get("enrolment"))
        return Response([{"id": str(vm.id), "lab": vm.lab.name, "description": vm.lab.description,
                          "status": vm.status, "image": vm.image, "access": ms.access(vm)} for vm in machines])

    @resaas_action(detail=True, methods=["post"], label="Renew my password", icon="key",
                   permission="renew_own_password_virtualmachine", visible=False)
    def renew_own_password(self, request, pk=None):
        _, machines = self._own(request, request.data.get("enrolment"))
        vm = machines.filter(id=pk).first()
        if vm is None:
            raise ResaasAPIException("Machine not found.", code="not_found", status_code=404)
        return Response({"password": ms.renew_password(vm=vm, user=request.user, request=request)})
