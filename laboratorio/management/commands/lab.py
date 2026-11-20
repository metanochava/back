"""manage.py lab - the former lab-manager/lab.sh, now laboratorio's command.

The same groups and safety rules as lab.sh (docs/modules/laboratorio.md):

    lab doctor | status | paths
    lab lab list | create <name> --entity E --branch B [--class-group ID] [--image I]
    lab lab network-mode <lab> <shared|isolated>
    lab image list | build <image:tag> [--context DIR]
    lab network list | info <lab> | prune [--apply]
    lab machine list [--lab L] | info <container> | stats [<container>]
    lab machine create <lab> <username> [--image] [--ram] [--cpus]
    lab machine create-group <lab> [--image] [--ram] [--cpus]       (the lab's class)
    lab machine start|stop|restart <container> | start-group|stop-group|restart-group <lab>
    lab machine shell <container> [command...]
    lab machine password <container>
    lab machine delete <container> [--purge-volume] [--cleanup] [--dry-run] [--yes]
    lab sync
    lab backup <container> | backup-all | backups <container> | restore <container> <file> [--yes]
    lab storage audit | cleanup [--apply --purge-orphans]
    lab history [--limit N]
    lab import-legacy --sqlite PATH --entity E --branch B [--dry-run]

Destructive operations describe themselves first and need --yes (or a
terminal answer); volumes are kept unless --purge-volume; nothing without the
lab.manager label is touched; there is no global docker prune. Every change
is an AuditLog row. Passwords are printed once and never stored.
"""
import os
import shutil
import sqlite3
import subprocess
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from django_resaas.saas.core.exceptions import ResaasAPIException
from django_resaas.saas.core.services import audit_service
from django_resaas.saas.models.audit_log import AuditLog

from laboratorio.models import Environment, VirtualLab, VirtualMachine
from laboratorio.services import docker_client as docker
from laboratorio.services import machine_service as ms

IMAGE_CONTEXT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docker", "ubuntu")


class Command(BaseCommand):
    help = "Virtual labs and machines (the former lab-manager/lab.sh)."

    # ------------------------------------------------------------ arguments

    def add_arguments(self, parser):
        groups = parser.add_subparsers(dest="group", required=True)
        for name in ("doctor", "status", "paths", "sync", "backup-all"):
            groups.add_parser(name)
        history = groups.add_parser("history")
        history.add_argument("--limit", type=int, default=50)

        lab = groups.add_parser("lab").add_subparsers(dest="cmd", required=True)
        lab.add_parser("list")
        create = lab.add_parser("create")
        create.add_argument("name")
        self._tenant(create)
        create.add_argument("--class-group")
        create.add_argument("--image")
        create.add_argument("--description", default="")
        mode = lab.add_parser("network-mode")
        mode.add_argument("lab")
        mode.add_argument("mode", choices=("shared", "isolated"))

        image = groups.add_parser("image").add_subparsers(dest="cmd", required=True)
        image.add_parser("list")
        build = image.add_parser("build")
        build.add_argument("image")
        build.add_argument("--context", default=IMAGE_CONTEXT)

        network = groups.add_parser("network").add_subparsers(dest="cmd", required=True)
        network.add_parser("list")
        info = network.add_parser("info")
        info.add_argument("lab")
        prune = network.add_parser("prune")
        prune.add_argument("--apply", action="store_true")

        machine = groups.add_parser("machine").add_subparsers(dest="cmd", required=True)
        ls = machine.add_parser("list")
        ls.add_argument("--lab")
        for name in ("info", "start", "stop", "restart", "password"):
            machine.add_parser(name).add_argument("container")
        st = machine.add_parser("stats")
        st.add_argument("container", nargs="?")
        for name in ("start-group", "stop-group", "restart-group"):
            machine.add_parser(name).add_argument("lab")
        mc = machine.add_parser("create")
        mc.add_argument("lab")
        mc.add_argument("username")
        group = machine.add_parser("create-group")
        group.add_argument("lab")
        for sub in (mc, group):
            sub.add_argument("--image")
            sub.add_argument("--ram")
            sub.add_argument("--cpus")
        shell = machine.add_parser("shell")
        shell.add_argument("container")
        shell.add_argument("command", nargs="*")
        delete = machine.add_parser("delete")
        delete.add_argument("container")
        delete.add_argument("--purge-volume", action="store_true")
        delete.add_argument("--cleanup", action="store_true")
        delete.add_argument("--dry-run", action="store_true")
        delete.add_argument("--yes", action="store_true")

        groups.add_parser("backup").add_argument("container")
        groups.add_parser("backups").add_argument("container")
        restore = groups.add_parser("restore")
        restore.add_argument("container")
        restore.add_argument("file")
        restore.add_argument("--yes", action="store_true")

        storage = groups.add_parser("storage").add_subparsers(dest="cmd", required=True)
        storage.add_parser("audit")
        cleanup = storage.add_parser("cleanup")
        cleanup.add_argument("--apply", action="store_true")
        cleanup.add_argument("--purge-orphans", action="store_true")

        legacy = groups.add_parser("import-legacy")
        legacy.add_argument("--sqlite", required=True)
        self._tenant(legacy)
        legacy.add_argument("--dry-run", action="store_true")

    @staticmethod
    def _tenant(parser):
        parser.add_argument("--entity", required=True, help="Entity name or id")
        parser.add_argument("--branch", required=True, help="Branch name or id (of that Entity)")

    # ------------------------------------------------------------ helpers

    def handle(self, *args, **opts):
        method = "_" + "_".join(filter(None, (opts["group"], opts.get("cmd")))).replace("-", "_")
        try:
            getattr(self, method)(opts)
        except ResaasAPIException as exc:
            details = getattr(exc, "details", None)
            raise CommandError(f"{exc}{f' {details}' if details else ''}")
        except docker.DockerError as exc:
            raise CommandError(f"{exc} {exc.stderr}".strip())

    def ok(self, message):
        self.stdout.write(self.style.SUCCESS(f"✅ {message}"))

    def table(self, rows, columns):
        if not rows:
            self.stdout.write("(none)")
            return
        widths = [max(len(str(c)), *(len(str(r.get(c, "") or "")) for r in rows)) for c in columns]
        self.stdout.write("  ".join(str(c).upper().ljust(w) for c, w in zip(columns, widths)))
        for r in rows:
            self.stdout.write("  ".join(str(r.get(c, "") or "").ljust(w) for c, w in zip(columns, widths)))

    def confirm(self, opts, question):
        if opts.get("yes"):
            return True
        if not sys.stdin.isatty():
            raise CommandError("Not interactive: check the operation, then use --yes.")
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "s", "sim")

    @staticmethod
    def tenant(opts):
        from django_resaas.saas.models.branch import Branch
        from django_resaas.saas.models.entity import Entity

        entity = (Entity.objects.filter(id=opts["entity"]).first() if len(opts["entity"]) == 36
                  else Entity.objects.filter(name=opts["entity"]).first())
        if entity is None:
            raise CommandError(f"Entity not found: {opts['entity']}")
        branches = Branch.objects.filter(entity=entity)
        branch = (branches.filter(id=opts["branch"]).first() if len(opts["branch"]) == 36
                  else branches.filter(name=opts["branch"]).first())
        if branch is None:
            raise CommandError(f"Branch not found in {entity.name}: {opts['branch']}")
        return entity, branch

    @staticmethod
    def lab(name):
        lab = VirtualLab.objects.filter(name=ms.sanitize(name)).first()
        if lab is None:
            raise CommandError(f"Lab not found: {name}")
        return lab

    @staticmethod
    def vm(container):
        vm = VirtualMachine.objects.filter(container_name=ms.sanitize(container), removed_at__isnull=True) \
            .select_related("lab").first()
        if vm is None:
            raise CommandError(f"Machine not found: {container}")
        return vm

    def print_access(self, vm, password=None):
        access = ms.access(vm)
        self.stdout.write(f"  SSH:  {access['ssh']}")
        if password:
            self.stdout.write(f"  Password (shown once, not stored): {password}")
        self.stdout.write(f"  HTTP: {access['http']}")

    # ------------------------------------------------------------ general

    def _doctor(self, opts):
        failed = False
        for cmd in ("docker", "tar"):
            path = shutil.which(cmd)
            self.stdout.write(f"{'✅' if path else '❌'} {cmd:<8} {path or 'not found'}")
            failed |= not path
        reachable = docker.ok(["info"])
        self.stdout.write(f"{'✅' if reachable else '❌'} Docker daemon {'reachable' if reachable else 'not reachable'}")
        image = settings.LABORATORIO["DEFAULT_IMAGE"]
        has_image = reachable and docker.image_exists(image)
        self.stdout.write(f"{'✅' if has_image else '⚠️ '} default image {image}")
        self.stdout.write(f"   backups: {ms.backup_dir()}  public host: {settings.LABORATORIO['PUBLIC_HOST'] or '(LAB_PUBLIC_HOST unset)'}")
        if failed or not reachable:
            raise CommandError("The diagnosis found problems.")
        self.ok("Diagnosis without critical errors.")

    def _paths(self, opts):
        self.stdout.write(f"image context: {IMAGE_CONTEXT}\nbackups:       {ms.backup_dir()}")

    def _status(self, opts):
        _, out, _ = docker.run(["ps", "-a", "--filter", "label=lab.manager=true", "--format",
                                "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])
        self.stdout.write(out)
        self.stdout.write(docker.run(["system", "df"])[1])

    def _sync(self, opts):
        counts = ms.sync()
        self.ok(f"Synchronised: {counts}")

    def _history(self, opts):
        rows = AuditLog.objects.filter(action__startswith="LAB_").order_by("-id")[:opts["limit"]]
        self.table([{"when": r.created_at if hasattr(r, "created_at") else "", "action": r.action, "model": r.model,
                     "object": r.object_id, "details": r.details or ""} for r in rows],
                   ["when", "action", "model", "object", "details"])

    # ------------------------------------------------------------ labs

    def _lab_list(self, opts):
        self.table([{"name": lab.name, "entity": lab.entity.name, "mode": lab.network_mode, "network": lab.network_name,
                     "class": lab.class_group.name if lab.class_group_id else "",
                     "machines": lab.machines.filter(removed_at__isnull=True).count()}
                    for lab in VirtualLab.objects.select_related("entity", "class_group")],
                   ["name", "entity", "mode", "network", "class", "machines"])

    def _lab_create(self, opts):
        entity, branch = self.tenant(opts)
        environment = None
        if opts.get("image"):
            environment, _ = Environment.objects.get_or_create(entity=entity, branch=branch, name=opts["image"],
                                                               defaults={"image": opts["image"]})
        class_group = None
        if opts.get("class_group"):
            from academica.models import ClassGroup

            class_group = ClassGroup.objects.filter(id=opts["class_group"], entity=entity).first()
            if class_group is None:
                raise CommandError("Class not found in this Entity.")
        lab = VirtualLab.objects.create(entity=entity, branch=branch, name=ms.sanitize(opts["name"]),
                                        description=opts["description"], class_group=class_group,
                                        environment=environment)
        ms.ensure_shared_network(lab)
        audit_service.record(action="LAB_VM_LAB_CREATED", target=lab, entity_id=entity.id, details={"name": lab.name})
        self.ok(f"Lab created: {lab.name} (network {lab.network_name})")

    def _lab_network_mode(self, opts):
        for row in ms.set_network_mode(lab=self.lab(opts["lab"]), mode=opts["mode"]):
            self.stdout.write(f"  {row['container']:<28} -> {row['network']}")
        self.ok(f"Network mode: {opts['mode']}")

    # ------------------------------------------------------------ images / networks

    def _image_list(self, opts):
        self.table([{"image": f"{i['Repository']}:{i['Tag']}", "id": i["ID"], "size": i["Size"],
                     "created": i["CreatedSince"]} for i in docker.images()], ["image", "id", "size", "created"])

    def _image_build(self, opts):
        if not os.path.isfile(os.path.join(opts["context"], "Dockerfile")):
            raise CommandError(f"No Dockerfile in {opts['context']}")
        # streamed: a build takes minutes
        code = subprocess.call(["docker", "build", "--no-cache", "--pull", "-t", opts["image"], opts["context"]])
        if code:
            raise CommandError("The build failed.")
        self.ok(f"Image built: {opts['image']}")

    def _network_list(self, opts):
        self.table([{"network": n, "containers": docker.network_container_count(n)} for n in docker.managed("network")],
                   ["network", "containers"])

    def _network_info(self, opts):
        lab = self.lab(opts["lab"])
        self.stdout.write(f"Lab: {lab.name}  mode: {lab.network_mode}")
        self.table([{"container": vm.container_name, "user": vm.username, "status": vm.status,
                     "network": vm.network_name} for vm in lab.machines.filter(removed_at__isnull=True)],
                   ["container", "user", "status", "network"])

    def _network_prune(self, opts):
        empty = ms.empty_networks()
        self.stdout.write("Managed networks without containers: " + (", ".join(empty) or "none"))
        if not opts["apply"]:
            self.stdout.write("Dry run: nothing removed (use --apply to remove only these networks).")
            return
        if not self.confirm(opts, "Remove only these empty Lab networks?"):
            return
        self.ok(f"Removed: {', '.join(ms.remove_empty_networks()) or 'none'}")

    # ------------------------------------------------------------ machines

    def _machine_list(self, opts):
        rows = VirtualMachine.objects.filter(removed_at__isnull=True).select_related("lab", "enrolment__student__person")
        if opts.get("lab"):
            rows = rows.filter(lab__name=ms.sanitize(opts["lab"]))
        self.table([{"container": vm.container_name, "lab": vm.lab.name, "user": vm.username,
                     "student": vm.enrolment.student.person.full_name if vm.enrolment_id else "-",
                     "status": vm.status, "ssh": vm.ssh_port, "http": vm.http_port, "image": vm.image} for vm in rows],
                   ["container", "lab", "user", "student", "status", "ssh", "http", "image"])

    def _machine_info(self, opts):
        vm = self.vm(opts["container"])
        for key in ("container_name", "username", "image", "ram", "cpus", "status", "volume_name", "network_name",
                    "ssh_port", "http_port", "https_port", "synced_at"):
            self.stdout.write(f"{key:<15} {getattr(vm, key)}")
        self.stdout.write(f"{'lab':<15} {vm.lab.name}")
        self.print_access(vm)

    def _machine_stats(self, opts):
        rows = VirtualMachine.objects.all()
        if opts.get("container"):
            rows = rows.filter(container_name=ms.sanitize(opts["container"]))
        self.table([{"name": r["Name"], "cpu": r["CPUPerc"], "memory": r["MemUsage"], "mem%": r["MemPerc"],
                     "net": r["NetIO"], "block": r["BlockIO"], "pids": r["PIDs"]} for r in ms.stats(rows)],
                   ["name", "cpu", "memory", "mem%", "net", "block", "pids"])

    def _machine_create(self, opts):
        vm, password = ms.create_machine(lab=self.lab(opts["lab"]), user=None, username=opts["username"],
                                         image=opts.get("image"), ram=opts.get("ram"), cpus=opts.get("cpus"))
        self.ok(f"Machine created: {vm.container_name}")
        self.print_access(vm, password)

    def _machine_create_group(self, opts):
        result = ms.create_for_class(lab=self.lab(opts["lab"]), user=None, image=opts.get("image"),
                                     ram=opts.get("ram"), cpus=opts.get("cpus"))
        for row in result["created"]:
            self.stdout.write(f"  {row['container']:<28} {row['username']:<20} password: {row['password']}")
        for row in result["failed"]:
            self.stderr.write(f"  ⚠️  {row['student']}: {row['error']}")
        self.ok(f"Group processed: created={len(result['created'])} failed={len(result['failed'])}")

    def _power(self, opts, action):
        ms.power(vm=self.vm(opts["container"]), action=action)
        self.ok(f"Machine {action}: {opts['container']}")

    def _machine_start(self, opts):
        self._power(opts, "start")

    def _machine_stop(self, opts):
        self._power(opts, "stop")

    def _machine_restart(self, opts):
        self._power(opts, "restart")

    def _power_lab(self, opts, action):
        result = ms.power_lab(lab=self.lab(opts["lab"]), action=action)
        for row in result["failed"]:
            self.stderr.write(f"  ⚠️  {row['container']}: {row['error']}")
        self.ok(f"{action}: {len(result['done'])} machines")

    def _machine_start_group(self, opts):
        self._power_lab(opts, "start")

    def _machine_stop_group(self, opts):
        self._power_lab(opts, "stop")

    def _machine_restart_group(self, opts):
        self._power_lab(opts, "restart")

    def _machine_password(self, opts):
        vm = self.vm(opts["container"])
        password = ms.renew_password(vm=vm)
        self.ok(f"Password renewed: {vm.container_name}")
        self.stdout.write(f"  New password (shown once, not stored): {password}")

    def _machine_shell(self, opts):
        vm = self.vm(opts["container"])
        if not docker.container_running(vm.container_name):
            raise CommandError(f"The machine is not running: {vm.container_name}")
        command = opts["command"] or (["/bin/bash"] if docker.ok(["exec", vm.container_name, "test", "-x", "/bin/bash"])
                                      else ["/bin/sh"])
        audit_service.record(action="LAB_VM_SHELL", target=vm, entity_id=vm.entity_id,
                             details={"command": " ".join(command)[:300]})
        raise SystemExit(subprocess.call(["docker", "exec", "-it", vm.container_name, *command]))

    def _machine_delete(self, opts):
        vm = self.vm(opts["container"])
        plan = ms.delete_plan(vm, opts["purge_volume"])
        self.stdout.write(f"Machine: {vm.container_name}\nLab: {vm.lab.name}\nUser: {vm.username}\n"
                          f"Volume: {vm.volume_name or '-'}\nNetworks: {', '.join(plan['networks']) or '-'}\n"
                          f"Persistent data: {'WILL BE DELETED' if not plan['volume_kept'] else 'kept'}")
        if opts["dry_run"]:
            self.stdout.write("Preview only: nothing changed.")
            return
        if not self.confirm(opts, f"Delete the machine '{vm.container_name}'?"):
            self.stdout.write("Cancelled.")
            return
        ms.delete(vm=vm, purge_volume=opts["purge_volume"], cleanup=opts["cleanup"])
        self.ok(f"Machine deleted: {vm.container_name}" + ("" if opts["purge_volume"] else f" (volume kept: {vm.volume_name})"))

    # ------------------------------------------------------------ backups / storage

    def _backup(self, opts):
        self.ok(f"Backup: {ms.backup(vm=self.vm(opts['container']))}")

    def _backup_all(self, opts):
        for vm in VirtualMachine.objects.filter(removed_at__isnull=True).select_related("lab"):
            try:
                self.ok(f"Backup: {ms.backup(vm=vm)}")
            except ResaasAPIException as exc:
                self.stderr.write(f"  ⚠️  {vm.container_name}: {exc}")

    def _backups(self, opts):
        for name in ms.backups(self.vm(opts["container"])):
            self.stdout.write(name)

    def _restore(self, opts):
        vm = self.vm(opts["container"])
        if not self.confirm(opts, f"Replace the home of '{vm.container_name}' with {opts['file']}?"):
            return
        ms.restore(vm=vm, file_name=opts["file"])
        self.ok(f"Backup restored in {vm.container_name}")

    def _storage_audit(self, opts):
        audit = ms.storage_audit()
        self.table(audit["volumes"], ["volume", "active", "referenced", "containers"])
        if audit["missing"]:
            self.stdout.write("\nRegistered but missing in Docker:")
            self.table(audit["missing"], ["container", "volume"])

    def _storage_cleanup(self, opts):
        orphans = ms.orphan_volumes()
        self.stdout.write("Orphan volumes: " + (", ".join(orphans) or "none"))
        if not opts["apply"]:
            self.stdout.write("Dry run. To remove them: storage cleanup --apply --purge-orphans")
            return
        if not opts["purge_orphans"]:
            self.stdout.write("Nothing removed: add --purge-orphans to authorise orphan volumes.")
            return
        if not sys.stdin.isatty():
            raise CommandError("Removing volumes needs an interactive terminal.")
        if input("WARNING: remove orphan volumes (no machine, no container)? [y/N] ").strip().lower() not in ("y", "yes", "s", "sim"):
            return
        self.ok(f"Removed: {', '.join(ms.remove_orphan_volumes()) or 'none'}")

    # ------------------------------------------------------------ legacy import

    def _import_legacy(self, opts):
        """The former lab-manager SQLite (labs, machines, history) into the
        models, idempotent by name. Containers are never touched; passwords
        are not imported (renew them per machine); history becomes AuditLog
        rows LAB_LEGACY_<ACTION>."""
        entity, branch = self.tenant(opts)
        path = opts["sqlite"]
        if not os.path.isfile(path):
            raise CommandError(f"Not found: {path}")
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        labs = db.execute("SELECT * FROM labs ORDER BY id").fetchall()
        machines = db.execute("SELECT * FROM machines ORDER BY id").fetchall()
        history = db.execute("SELECT * FROM history ORDER BY id").fetchall()
        db.close()
        self.stdout.write(f"Legacy: {len(labs)} labs, {len(machines)} machines, {len(history)} history rows")
        if opts["dry_run"]:
            for m in machines:
                self.stdout.write(f"  {m['container_name']:<24} {m['lab_name']:<10} {m['status']}")
            self.stdout.write("Dry run: nothing imported.")
            return

        def when(value):
            parsed = parse_datetime(value.replace(" ", "T")) if value else None
            if parsed and timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed)
            return parsed

        made = {"labs": 0, "machines": 0, "history": 0}
        with transaction.atomic():
            by_name = {}
            for row in labs:
                lab = VirtualLab.all_objects.filter(name=row["name"]).first()
                if lab is None:
                    lab = VirtualLab.objects.create(entity=entity, branch=branch, name=row["name"],
                                                    description=row["description"] or "",
                                                    network_mode=row["network_mode"] or "shared",
                                                    network_name=row["network_name"] or "")
                    made["labs"] += 1
                elif lab.entity_id != entity.id:
                    raise CommandError(f"The lab '{row['name']}' belongs to another Entity.")
                by_name[row["name"]] = lab
            for row in machines:
                if VirtualMachine.all_objects.filter(container_name=row["container_name"], entity=entity).exists():
                    continue
                deleted = when(row["deleted_at"])
                vm = VirtualMachine.objects.create(
                    entity=entity, branch=branch, lab=by_name[row["lab_name"]], username=row["student_username"],
                    container_name=row["container_name"], image=row["image"], ram=row["ram"], cpus=row["cpus"],
                    ssh_port=row["ssh_port"], http_port=row["http_port"], https_port=row["https_port"],
                    status=row["status"] if row["status"] in dict(VirtualMachine.STATUS_CHOICES) else "missing",
                    volume_name=row["volume_name"] or "", network_name=row["network_name"] or "",
                    removed_at=deleted,
                )
                VirtualMachine.objects.filter(pk=vm.pk).update(created_at=when(row["created_at"]) or timezone.now())
                made["machines"] += 1
            if not AuditLog.objects.filter(action__startswith="LAB_LEGACY_", entity_id=entity.id).exists():
                for row in history:
                    target = (VirtualMachine.all_objects.filter(container_name=row["container_name"]).first()
                              if row["container_name"] else None) or by_name.get(row["lab_name"]) \
                        or next(iter(by_name.values()), None)
                    if target is None:
                        continue
                    audit_service.record(action=f"LAB_LEGACY_{row['action'].upper().replace('-', '_')}"[:50],
                                         target=target, entity_id=entity.id,
                                         details={"at": row["created_at"], "container": row["container_name"],
                                                  "lab": row["lab_name"], "student": row["student_username"],
                                                  "message": row["message"]})
                    made["history"] += 1
        counts = ms.sync(VirtualMachine.objects.filter(entity=entity))
        self.ok(f"Imported: {made}; Docker state now: {counts}")
