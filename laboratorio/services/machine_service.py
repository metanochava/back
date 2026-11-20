"""Virtual labs and their machines: the former lab-manager/lab.sh, in the
laboratorio module.

The same Docker rules as lab.sh:

- one container per student and lab, "<lab>-<user>", with a persistent home
  volume "<volume prefix>-<container>-home" and labels lab.manager=true,
  lab.name, lab.student, lab.volume (plus lab.entity: two Entities never
  collide nor see each other's machines);
- SSH / HTTP on ports Docker assigns (-p 22 / 80; 443 only with
  LAB_HTTPS_ENABLED=true - nothing in the image serves it), read back with
  `docker port`;
- the network is the lab's shared "<network prefix>-<lab>" or, in isolated
  mode, one "<network prefix>-<container>" per machine;
- deleting a machine keeps its volume unless purge_volume (and never a
  volume another container uses); a dry run only describes; storage cleanup
  and prune remove nothing without apply, never touch objects without the
  lab.manager label, never run a global docker prune.

What changed: state lives in the laboratorio models (Entity / Branch
scoped), history in the AuditLog (LAB_VM_*), and the password is never
stored - it is returned once by create_machine() / renew_password().
"""
import os
import re
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services import audit_service

from laboratorio.models import VirtualLab, VirtualMachine
from laboratorio.services import docker_client as docker
from laboratorio.services.docker_client import DockerError

USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,59}$")
RAM = re.compile(r"^[1-9][0-9]*(k|m|g|t)?$")
CPUS = re.compile(r"^([1-9][0-9]*|[0-9]+\.[0-9]+)$")


def conf(key):
    return settings.LABORATORIO[key]


def _error(message, field=None, code="invalid", status_code=400):
    return ResaasAPIException(message, code=code, status_code=status_code,
                              details={field: [message]} if field else None)


def _docker_failed(exc):
    return ResaasAPIException("Docker could not complete the operation.", code="docker_failed", status_code=502,
                              details={"docker": [str(exc)]})


def sanitize(value):
    """lab.sh sanitize(): lowercase, [a-z0-9_-] only, no repeated / edge '-'."""
    value = re.sub(r"-+", "-", re.sub(r"[^a-z0-9_-]", "-", str(value or "").lower())).strip("-")
    if not value:
        raise _error("Invalid name.", "name")
    return value


def validate_resources(ram, cpus):
    if not RAM.match(str(ram)):
        raise _error("Invalid RAM (e.g. 512m, 1g, 2g).", "ram")
    if not CPUS.match(str(cpus)) or not 0 < float(cpus) <= 128:
        raise _error("Invalid CPUs (e.g. 1, 2, 0.5; at most 128).", "cpus")


def random_password():
    return secrets.token_hex(8)


def username_for(enrolment):
    """A student's SSH user: their first name and the end of their number
    (e.g. tito-00001); the image wants it to start with a letter."""
    person = enrolment.student.person
    first = re.sub(r"[^a-z]", "", sanitize(person.name or "student").replace("-", "")) or "student"
    digits = re.sub(r"\D", "", enrolment.student.number or "")[-5:]
    return f"{first[:40]}-{digits}" if digits else first[:40]


def _audit(action, target, user=None, request=None, **details):
    audit_service.record(action=action, target=target, actor=user, request=request, entity_id=target.entity_id,
                         details=details or None)


def _labels(lab, **extra):
    labels = {"lab.manager": "true", "lab.name": lab.name, "lab.entity": str(lab.entity_id), **extra}
    return [arg for key, value in labels.items() for arg in ("--label", f"{key}={value}")]


# ------------------------------------------------------------------ networks


def shared_network_name(lab):
    return f"{conf('NETWORK_PREFIX')}-{lab.name}"


def ensure_shared_network(lab):
    name = shared_network_name(lab)
    if not docker.network_exists(name):
        docker.run(["network", "create", "--driver", "bridge", *_labels(lab), name])
    if lab.network_name != name:
        VirtualLab.objects.filter(pk=lab.pk).update(network_name=name)
        lab.network_name = name
    return name


def ensure_isolated_network(lab, container):
    name = f"{conf('NETWORK_PREFIX')}-{container}"
    if not docker.network_exists(name):
        docker.run(["network", "create", "--driver", "bridge",
                    *_labels(lab, **{"lab.mode": "isolated", "lab.container": container}), name])
    return name


def network_for(lab, container):
    if lab.network_mode == VirtualLab.MODE_ISOLATED:
        return ensure_isolated_network(lab, container)
    return ensure_shared_network(lab)


def set_network_mode(*, lab, mode, user=None, request=None):
    """Move every machine of the lab to the shared network or to its own."""
    if mode not in (VirtualLab.MODE_SHARED, VirtualLab.MODE_ISOLATED):
        raise _error("Invalid network mode: use shared or isolated.", "network_mode")
    shared = shared_network_name(lab)
    lab.network_mode = mode
    try:
        if mode == VirtualLab.MODE_SHARED:
            ensure_shared_network(lab)
        moved = []
        for vm in lab.machines.filter(removed_at__isnull=True):
            target = (ensure_isolated_network(lab, vm.container_name) if mode == VirtualLab.MODE_ISOLATED
                      else shared)
            if docker.container_exists(vm.container_name):
                current = docker.container_networks(vm.container_name)
                if target not in current:
                    docker.run(["network", "connect", target, vm.container_name])
                for old in current:
                    if old != target and old.startswith(conf("NETWORK_PREFIX")):
                        docker.run(["network", "disconnect", old, vm.container_name], check=False)
            VirtualMachine.objects.filter(pk=vm.pk).update(network_name=target, updated_at=timezone.now())
            moved.append({"container": vm.container_name, "network": target})
    except DockerError as exc:
        raise _docker_failed(exc)
    VirtualLab.objects.filter(pk=lab.pk).update(network_mode=mode, network_name=shared, updated_at=timezone.now())
    lab.network_name = shared
    _audit("LAB_VM_NETWORK_MODE", lab, user, request, mode=mode)
    return moved


# ------------------------------------------------------------------ machines


def _check_create(lab, username, enrolment):
    if enrolment is not None:
        if enrolment.entity_id != lab.entity_id:
            raise _error("Does not belong to the current entity.", "enrolment")
        if lab.machines.filter(enrolment=enrolment, removed_at__isnull=True).exists():
            raise _error("The student already has a machine in this lab.", "enrolment", code="already_exists",
                         status_code=409)
    if not USERNAME.match(username):
        raise _error("Invalid username: start with a letter; a-z, 0-9, _ and - only.", "username")


def create_machine(*, lab, user, enrolment=None, username=None, image=None, ram=None, cpus=None, request=None):
    """Make a student's machine and start it. Returns (machine, password):
    the password is shown to the caller once and never stored."""
    username = sanitize(username) if username else username_for(enrolment) if enrolment else None
    if not username:
        raise _error("Choose a student or a username.", "username")
    _check_create(lab, username, enrolment)
    image = image or (lab.environment.image if lab.environment_id and lab.environment.image else conf("DEFAULT_IMAGE"))
    ram, cpus = ram or conf("RAM"), str(cpus or conf("CPUS"))
    validate_resources(ram, cpus)
    container = f"{lab.name}-{username}"
    if VirtualMachine.objects.filter(container_name=container, removed_at__isnull=True).exists():
        raise _error("A machine with this name already exists.", "username", code="already_exists", status_code=409)
    password = random_password()
    exposed = (22, 80, 443) if conf("HTTPS_ENABLED") else (22, 80)     # 443 only when the image serves it
    auth = conf("SSH_PASSWORD_AUTH")
    sudo = conf("SUDO")
    if auth not in ("yes", "no") or sudo not in ("true", "false"):
        raise _error("LAB_SSH_PASSWORD_AUTH must be yes / no and LAB_SUDO true / false.", code="misconfigured",
                     status_code=500)
    try:
        if not docker.image_exists(image):
            raise _error("Docker image not found: build it first.", "image", code="image_missing", status_code=409)
        if docker.container_exists(container):
            raise _error("A machine with this name already exists.", "username", code="already_exists",
                         status_code=409)
        network = network_for(lab, container)
        volume = f"{conf('VOLUME_PREFIX')}-{container}-home"
        if not docker.volume_exists(volume):
            docker.run(["volume", "create", *_labels(lab, **{"lab.student": username, "lab.container": container}),
                        volume])
        docker.run([
            "run", "-dit", "--name", container, "--hostname", container, f"--memory={ram}", f"--cpus={cpus}",
            "--restart", conf("RESTART_POLICY"), "--network", network,
            *_labels(lab, **{"lab.student": username, "lab.volume": volume}),
            "-e", f"SSH_USER={username}", "-e", f"LAB_USER={username}",
            "-e", f"SSH_PASSWORD={password}", "-e", f"LAB_PASSWORD={password}",
            "-e", f"LAB_SUDO={sudo}", "-e", f"LAB_SSH_PASSWORD_AUTH={auth}", "-e", "LAB_SSH_ROOT_LOGIN=no",
            "-e", f"LAB_SSH_AUTHORIZED_KEYS={conf('SSH_AUTHORIZED_KEYS')}",
            "-v", f"{volume}:/home/{username}", *[arg for port in exposed for arg in ("-p", f"{port}/tcp")], image,
        ])
        if not docker.container_running(container):
            docker.run(["rm", "-f", container], check=False)          # the volume is kept
            raise _error("The machine did not start; its volume was kept.", code="machine_failed", status_code=502)
        ports = {p: docker.published_port(container, p) for p in exposed}
    except DockerError as exc:
        raise _docker_failed(exc)
    with transaction.atomic():
        vm = VirtualMachine.objects.create(
            entity_id=lab.entity_id, branch_id=lab.branch_id, created_by=user, updated_by=user,
            lab=lab, enrolment=enrolment, username=username, container_name=container, image=image, ram=ram,
            cpus=cpus, ssh_port=ports[22], http_port=ports[80], https_port=ports.get(443),
            status=VirtualMachine.STATUS_RUNNING, volume_name=volume, network_name=network,
            synced_at=timezone.now(),
        )
        _audit("LAB_VM_CREATED", vm, user, request, container=container, image=image, ram=ram, cpus=cpus,
               enrolment_id=str(enrolment.id) if enrolment else None)
    return vm, password


def create_for_class(*, lab, user, image=None, ram=None, cpus=None, request=None):
    """A machine for every active student of the lab's class that has none
    (create-group). Returns {created: [{machine, username, password}], failed: [...]}."""
    from academica.models import Enrolment

    if not lab.class_group_id:
        raise _error("The lab has no class.", "class_group")
    created, failed = [], []
    for enrolment in (Enrolment.objects.filter(class_group_id=lab.class_group_id, status="active")
                      .exclude(virtual_machines__lab=lab, virtual_machines__removed_at__isnull=True)
                      .select_related("student__person")):
        try:
            vm, password = create_machine(lab=lab, user=user, enrolment=enrolment, image=image, ram=ram, cpus=cpus,
                                          request=request)
            created.append({"machine": str(vm.id), "container": vm.container_name, "username": vm.username,
                            "password": password})
        except ResaasAPIException as exc:
            failed.append({"enrolment": str(enrolment.id), "student": enrolment.student.person.full_name,
                           "error": str(exc)})
    _audit("LAB_VM_GROUP_CREATED", lab, user, request, created=len(created), failed=len(failed))
    return {"created": created, "failed": failed}


def _set_status(vm, status):
    VirtualMachine.objects.filter(pk=vm.pk).update(status=status, synced_at=timezone.now(), updated_at=timezone.now())
    vm.status = status


def power(*, vm, action, user=None, request=None):
    """start / stop / restart a machine."""
    if action not in ("start", "stop", "restart"):
        raise _error("Invalid action.", "action")
    if vm.removed_at:
        raise _error("The machine was deleted.", code="machine_deleted", status_code=409)
    try:
        if not docker.container_exists(vm.container_name):
            _set_status(vm, VirtualMachine.STATUS_MISSING)
            raise _error("The machine's container is missing.", code="machine_missing", status_code=409)
        docker.run([action, vm.container_name])
    except DockerError as exc:
        raise _docker_failed(exc)
    _set_status(vm, VirtualMachine.STATUS_STOPPED if action == "stop" else VirtualMachine.STATUS_RUNNING)
    _audit(f"LAB_VM_{action.upper()}", vm, user, request, container=vm.container_name)
    return vm


def power_lab(*, lab, action, user=None, request=None):
    done, failed = [], []
    for vm in lab.machines.filter(removed_at__isnull=True):
        try:
            power(vm=vm, action=action, user=user, request=request)
            done.append(vm.container_name)
        except ResaasAPIException as exc:
            failed.append({"container": vm.container_name, "error": str(exc)})
    return {"done": done, "failed": failed}


def delete_plan(vm, purge_volume=False):
    """What delete() would do (the dry run)."""
    exists = docker.container_exists(vm.container_name)
    volume_kept = not purge_volume
    if purge_volume and vm.volume_name and docker.volume_exists(vm.volume_name):
        if docker.volume_users(vm.volume_name) > 1:
            raise _error("The volume is used by other containers; it will not be removed.", "purge_volume",
                         code="volume_shared", status_code=409)
    return {"container": vm.container_name, "container_exists": exists, "volume": vm.volume_name,
            "volume_kept": volume_kept, "networks": docker.container_networks(vm.container_name) if exists else []}


def delete(*, vm, user=None, request=None, purge_volume=False, cleanup=False):
    try:
        plan = delete_plan(vm, purge_volume)
        if plan["container_exists"]:
            docker.run(["rm", "-f", vm.container_name])
        if purge_volume and vm.volume_name and docker.volume_exists(vm.volume_name):
            docker.run(["volume", "rm", vm.volume_name])
        if cleanup:
            for net in plan["networks"]:
                if net.startswith(conf("NETWORK_PREFIX")) and docker.network_container_count(net) == 0:
                    docker.run(["network", "rm", net], check=False)
    except DockerError as exc:
        raise _docker_failed(exc)
    now = timezone.now()
    VirtualMachine.objects.filter(pk=vm.pk).update(status=VirtualMachine.STATUS_DELETED, removed_at=now,
                                                   updated_at=now)
    vm.status, vm.removed_at = VirtualMachine.STATUS_DELETED, now
    _audit("LAB_VM_DELETED", vm, user, request, container=vm.container_name, purge_volume=purge_volume,
           cleanup=cleanup)
    return plan


def renew_password(*, vm, user=None, request=None):
    """A new password, set inside the running machine (chpasswd); returned once."""
    password = random_password()
    try:
        if not docker.container_running(vm.container_name):
            raise _error("Start the machine first.", code="machine_stopped", status_code=409)
        if not docker.ok(["exec", vm.container_name, "sh", "-c", "command -v chpasswd >/dev/null 2>&1"]):
            raise _error("The machine cannot change passwords (no chpasswd).", code="no_chpasswd", status_code=409)
        docker.run(["exec", "-i", vm.container_name, "chpasswd"], input=f"{vm.username}:{password}\n")
    except DockerError as exc:
        raise _docker_failed(exc)
    _audit("LAB_VM_PASSWORD_RENEWED", vm, user, request, container=vm.container_name)
    return password


def access(vm):
    """How to connect (never the password)."""
    host = conf("PUBLIC_HOST") or "<server>"
    return {"host": host, "username": vm.username, "ssh_port": vm.ssh_port, "http_port": vm.http_port,
            "https_port": vm.https_port,
            "ssh": f"ssh {vm.username}@{host} -p {vm.ssh_port}" if vm.ssh_port else "",
            "http": f"http://{host}:{vm.http_port}" if vm.http_port else ""}


def sync(queryset=None):
    """The real state of every machine (running / stopped / missing)."""
    counts = {"running": 0, "stopped": 0, "missing": 0}
    rows = (queryset if queryset is not None else VirtualMachine.objects).filter(removed_at__isnull=True)
    try:
        for vm in rows:
            if not docker.container_exists(vm.container_name):
                status = VirtualMachine.STATUS_MISSING
            elif docker.container_running(vm.container_name):
                status = VirtualMachine.STATUS_RUNNING
            else:
                status = VirtualMachine.STATUS_STOPPED
            _set_status(vm, status)
            counts[status] += 1
    except DockerError as exc:
        raise _docker_failed(exc)
    return counts


def stats(queryset):
    names = [vm.container_name for vm in queryset.filter(removed_at__isnull=True, status=VirtualMachine.STATUS_RUNNING)]
    try:
        return docker.stats(names)
    except DockerError as exc:
        raise _docker_failed(exc)


# ------------------------------------------------------------------ backups


def backup_dir():
    path = conf("BACKUP_DIR")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def backup(*, vm, user=None, request=None):
    """The machine's home volume as <container>_<YYYYmmdd_HHMMSS>.tar.gz."""
    if not vm.volume_name:
        raise _error("The machine has no volume.", code="no_volume", status_code=409)
    name = f"{vm.container_name}_{timezone.localtime():%Y%m%d_%H%M%S}.tar.gz"
    try:
        if not docker.volume_exists(vm.volume_name):
            raise _error("The machine's volume is missing.", code="volume_missing", status_code=409)
        docker.run(["run", "--rm", "-v", f"{vm.volume_name}:/source:ro", "-v", f"{backup_dir()}:/backup",
                    "alpine:latest", "tar", "czf", f"/backup/{name}", "-C", "/source", "."], timeout=1800)
    except DockerError as exc:
        raise _docker_failed(exc)
    _audit("LAB_VM_BACKUP", vm, user, request, file=name)
    return os.path.join(backup_dir(), name)


def backups(vm):
    prefix = f"{vm.container_name}_"
    return sorted((f for f in os.listdir(backup_dir()) if f.startswith(prefix) and f.endswith(".tar.gz")),
                  reverse=True)


def restore(*, vm, file_name, user=None, request=None):
    """Replace the home volume with one of the machine's own backups."""
    if os.path.basename(file_name) != file_name or file_name not in backups(vm):
        raise _error("Backup not found.", "file", code="not_found", status_code=404)
    try:
        if not docker.volume_exists(vm.volume_name):
            docker.run(["volume", "create", *_labels(vm.lab, **{"lab.student": vm.username,
                                                                 "lab.container": vm.container_name}),
                        vm.volume_name])
        docker.run(["run", "--rm", "-v", f"{vm.volume_name}:/target", "-v", f"{backup_dir()}:/backup:ro",
                    "alpine:latest", "sh", "-c",
                    'rm -rf /target/* /target/.[!.]* /target/..?* 2>/dev/null; cd /target && tar xzf "/backup/$0"',
                    file_name], timeout=1800)
    except DockerError as exc:
        raise _docker_failed(exc)
    _audit("LAB_VM_RESTORED", vm, user, request, file=file_name)
    return vm


# ------------------------------------------------------------------ storage


def storage_audit():
    """Managed volumes against the machines that reference them."""
    referenced = set(VirtualMachine.objects.exclude(volume_name="").values_list("volume_name", flat=True))
    active = set(VirtualMachine.objects.filter(removed_at__isnull=True).exclude(volume_name="")
                 .values_list("volume_name", flat=True))
    rows = []
    try:
        volumes = docker.managed("volume")
        for vol in volumes:
            rows.append({"volume": vol, "active": vol in active, "referenced": vol in referenced,
                         "containers": docker.volume_users(vol)})
    except DockerError as exc:
        raise _docker_failed(exc)
    missing = [{"container": c, "volume": v} for c, v in VirtualMachine.objects.filter(removed_at__isnull=True)
               .exclude(volume_name="").values_list("container_name", "volume_name") if v not in volumes]
    return {"volumes": rows, "missing": missing}


def orphan_volumes():
    """Managed volumes no machine references and no container uses."""
    return [r["volume"] for r in storage_audit()["volumes"] if not r["referenced"] and r["containers"] == 0]


def remove_orphan_volumes():
    removed = []
    try:
        for vol in orphan_volumes():
            code, out, _ = docker.run(["volume", "inspect", "--format", '{{ index .Labels "lab.manager" }}', vol],
                                      check=False)
            if code == 0 and out.strip() == "true":
                docker.run(["volume", "rm", vol])
                removed.append(vol)
    except DockerError as exc:
        raise _docker_failed(exc)
    return removed


def empty_networks():
    try:
        return [n for n in docker.managed("network") if docker.network_container_count(n) == 0]
    except DockerError as exc:
        raise _docker_failed(exc)


def remove_empty_networks():
    removed = []
    for net in empty_networks():
        if docker.ok(["network", "rm", net]):
            removed.append(net)
    return removed
