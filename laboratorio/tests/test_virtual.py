"""Virtual labs (the former Lab Manager) on a fake Docker: a machine per
student and lab with the lab.sh conventions (names, labels, volume, ports
Docker assigns), the password answered once and never stored, power and
missing containers, delete keeping the volume, the student's own machine and
password, Entity isolation, the network mode, and the legacy SQLite import."""
import datetime
import io
import json
import os
import sqlite3
import tempfile
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase

from academica import models as a
from academica.tests.test_enrolment import _audit, _client, _structure
from academica.tests.test_portal import _user_client
from django_resaas.saas.models.audit_log import AuditLog
from django_resaas.saas.models.person import Person
from laboratorio import models as m
from laboratorio.profiles import ACTION_PERMISSIONS, FAMILY, VIRTUAL_TECHNICIAN
from laboratorio.services import docker_client
from testutils.tenant import bootstrap_tenant

API = "/api/laboratorio/"


class FakeDocker:
    """Enough of the docker CLI for machine_service, in memory."""

    def __init__(self):
        self.images = {"ubuntu-lab:1"}
        self.containers = {}            # name -> {"running", "networks", "volume", "labels"}
        self.volumes = {}               # name -> labels
        self.networks = {}              # name -> labels
        self.calls = []
        self.port = 32800

    def __call__(self, args, *, input=None, timeout=None, check=True):
        self.calls.append((list(args), input))
        code, out = self.answer(list(args))
        if check and code:
            raise docker_client.DockerError(f"docker {args[0]} failed.")
        return code, out, ""

    @staticmethod
    def labels(args):
        return dict(args[i + 1].split("=", 1) for i, x in enumerate(args) if x == "--label")

    def answer(self, a):
        c = self.containers
        if a[:2] == ["image", "inspect"]:
            return (0 if a[2] in self.images else 1), ""
        if a[:2] == ["container", "inspect"]:
            return (0 if a[2] in c else 1), ""
        if a[0] == "inspect" and a[2] == "{{.State.Running}}":
            return (0, "true" if c[a[3]]["running"] else "false") if a[3] in c else (1, "")
        if a[0] == "inspect" and "Networks" in a[2]:
            return (0, json.dumps({n: {} for n in c[a[3]]["networks"]})) if a[3] in c else (1, "")
        if a[:2] == ["volume", "inspect"]:
            name = a[-1]
            if name not in self.volumes:
                return 1, ""
            return 0, self.volumes[name].get("lab.manager", "") if "--format" in a else ""
        if a[:2] == ["network", "inspect"]:
            name = a[-1]
            if name not in self.networks:
                return 1, ""
            return 0, str(sum(name in x["networks"] for x in c.values())) if "--format" in a else ""
        if a[:2] == ["network", "create"]:
            self.networks[a[-1]] = self.labels(a)
            return 0, ""
        if a[:2] == ["volume", "create"]:
            self.volumes[a[-1]] = self.labels(a)
            return 0, ""
        if a[0] == "run" and "-dit" in a:
            name = a[a.index("--name") + 1]
            volume = a[a.index("-v") + 1].split(":")[0]
            c[name] = {"running": True, "networks": [a[a.index("--network") + 1]], "volume": volume,
                       "labels": self.labels(a), "image": a[-1]}
            return 0, "id"
        if a[0] == "port":
            self.port += 1
            return (0, f"0.0.0.0:{self.port}\n") if a[1] in c else (1, "")
        if a[0] in ("start", "restart", "stop"):
            if a[1] not in c:
                return 1, ""
            c[a[1]]["running"] = a[0] != "stop"
            return 0, ""
        if a[:2] == ["rm", "-f"]:
            c.pop(a[2], None)
            return 0, ""
        if a[:2] == ["volume", "rm"]:
            self.volumes.pop(a[2], None)
            return 0, ""
        if a[0] == "exec":
            return 0, ""
        if a[:2] == ["network", "connect"]:
            c[a[3]]["networks"].append(a[2])
            return 0, ""
        if a[:2] == ["network", "disconnect"]:
            c[a[3]]["networks"].remove(a[2])
            return 0, ""
        if a[:2] == ["ps", "-a"] and a[3].startswith("volume="):
            return 0, "\n".join(n for n, x in c.items() if x["volume"] == a[3][7:])
        if a[:2] == ["ps", "-a"]:
            return 0, "\n".join(c)
        if a[1:2] == ["ls"]:
            return 0, "\n".join(self.volumes if a[0] == "volume" else self.networks)
        raise AssertionError(f"unexpected docker call: {a}")


def _action_permissions():
    for model, codenames in ACTION_PERMISSIONS.items():
        ct = ContentType.objects.get(app_label="laboratorio", model=model)
        for codename in codenames:
            Permission.objects.get_or_create(codename=codename, content_type=ct, defaults={"name": codename})
    Permission.objects.get_or_create(codename="view_own_enrolment", content_type=ContentType.objects.get(
        app_label="academica", model="enrolment"), defaults={"name": "view_own_enrolment"})


class VirtualLabTests(TestCase):

    def setUp(self):
        _action_permissions()
        self.docker = FakeDocker()
        patcher = mock.patch.object(docker_client, "run", self.docker)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tenant = bootstrap_tenant("vlab", modules=("academica", "laboratorio"))
        self.aud = _audit(self.tenant)
        self.s = _structure(self.tenant, capacity=10)
        self.tech = _client(self.tenant, VIRTUAL_TECHNICIAN)
        self.ana, ana = _user_client(self.tenant, [*FAMILY, "renew_own_password_virtualmachine"], "Ana")
        self.enrolment = self._enrol(ana, "2027-00007")

    def _enrol(self, person, number):
        student = a.Student.objects.create(person=person, number=number, admission_date=datetime.date(2027, 1, 5),
                                           **self.aud)
        return a.Enrolment.objects.create(student=student, academic_year=self.s["year"],
                                          programme=self.s["fifth"].programme, grade_level=self.s["fifth"],
                                          class_group=self.s["class_a"], status="active",
                                          enrolled_on=datetime.date(2027, 2, 1), **self.aud)

    def _lab(self, name="linux", **extra):
        response = self.tech.post(f"{API}virtuallabs/", {"name": name, "class_group": str(self.s["class_a"].id),
                                                         **extra}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.data["id"]

    def _machine(self, lab, expect=201, **body):
        response = self.tech.post(f"{API}virtualmachines/", {"lab": lab, "enrolment": str(self.enrolment.id), **body},
                                  format="json")
        self.assertEqual(response.status_code, expect, response.content)
        return response

    def test_a_machine_per_student_with_the_lab_sh_conventions_and_the_password_once(self):
        lab = self._lab()
        self.assertIn("labmgr-linux", self.docker.networks)                   # the lab's shared network
        created = self._machine(lab).data
        self.assertEqual(created["container_name"], "linux-ana-00007")
        self.assertEqual(len(created["password"]), 16)
        container = self.docker.containers["linux-ana-00007"]
        self.assertEqual(container["volume"], "labmgr-linux-ana-00007-home")
        self.assertEqual(container["labels"]["lab.entity"], str(self.tenant["entity"].id))
        self.assertTrue(created["ssh_port"] and created["http_port"])
        run = next(args for args, _ in self.docker.calls if args[0] == "run" and "-dit" in args)
        self.assertNotIn("443/tcp", run)                                     # nothing in the image serves HTTPS
        self.assertIsNone(created["https_port"])
        vm = m.VirtualMachine.objects.get(id=created["id"])
        self.assertFalse(any("password" in f.name for f in m.VirtualMachine._meta.fields))   # never stored
        self.assertNotIn(created["password"], json.dumps(self.tech.get(f"{API}virtualmachines/{vm.id}/").data,
                                                         default=str))
        self.assertTrue(AuditLog.objects.filter(object_id=str(vm.id), action="LAB_VM_CREATED").exists())
        self.assertNotIn(created["password"], json.dumps(list(AuditLog.objects.values_list("details", flat=True))))
        self._machine(lab, expect=409)                                       # one per student and lab
        self.docker.images.clear()
        bia = self._enrol(Person.objects.create(name="Bia", surname="X"), "2027-00008")
        self._machine(lab, expect=409, enrolment=str(bia.id))               # the image is missing

    def test_power_a_missing_container_and_delete_keeping_the_volume(self):
        vm = self._machine(self._lab()).data["id"]
        stopped = self.tech.post(f"{API}virtualmachines/{vm}/stop/", {}, format="json")
        self.assertEqual(stopped.data["status"]["value"] if isinstance(stopped.data["status"], dict)
                         else stopped.data["status"], "stopped")
        self.assertFalse(self.docker.containers["linux-ana-00007"]["running"])
        self.assertEqual(self.tech.delete(f"{API}virtualmachines/{vm}/").status_code, 204)
        self.assertNotIn("linux-ana-00007", self.docker.containers)
        self.assertIn("labmgr-linux-ana-00007-home", self.docker.volumes)    # kept
        self.assertIsNotNone(m.VirtualMachine.all_objects.get(id=vm).removed_at)
        # a container gone outside laboratorio: the machine becomes missing
        again = self._machine(str(m.VirtualLab.objects.get().id)).data["id"]         # its kept volume is reused
        self.docker.containers.clear()
        self.assertEqual(self.tech.post(f"{API}virtualmachines/{again}/start/", {}, format="json").status_code, 409)
        self.assertEqual(m.VirtualMachine.objects.get(id=again).status, "missing")

    def test_the_student_sees_their_machine_and_renews_their_own_password(self):
        vm = self._machine(self._lab()).data["id"]
        mine = self.ana.get(f"{API}virtualmachines/mine/", {"enrolment": str(self.enrolment.id)})
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.data[0]["access"]["username"], "ana-00007")
        self.assertNotIn("password", mine.data[0])
        renewed = self.ana.post(f"{API}virtualmachines/{vm}/renew_own_password/",
                                {"enrolment": str(self.enrolment.id)}, format="json")
        self.assertIn(renewed.status_code, (200, 202), renewed.content)
        self.assertIn(("ana-00007:" + renewed.data["password"] + "\n"),
                      [i for args, i in self.docker.calls if args[-1:] == ["chpasswd"]])
        self.assertEqual(self.ana.get(f"{API}virtualmachines/").status_code, 403)
        bia = self._enrol(Person.objects.create(name="Bia", surname="X"), "2027-00008")
        other = self._machine(str(m.VirtualLab.objects.get().id), enrolment=str(bia.id)).data["id"]
        self.assertEqual(self.ana.post(f"{API}virtualmachines/{other}/renew_own_password/",
                                       {"enrolment": str(self.enrolment.id)}, format="json").status_code, 404)
        self.assertEqual(self.ana.get(f"{API}virtualmachines/mine/", {"enrolment": str(bia.id)}).status_code, 404)

    def test_another_entitys_student_and_the_isolated_network_mode(self):
        lab = self._lab()
        other = bootstrap_tenant("vlab-other", modules=("academica", "laboratorio"))
        s2 = _structure(other)
        foreign = a.Enrolment.objects.create(
            student=a.Student.objects.create(person=Person.objects.create(name="Zed", surname="X"), number="9",
                                             admission_date=datetime.date(2027, 1, 5), **_audit(other)),
            academic_year=s2["year"], programme=s2["fifth"].programme, grade_level=s2["fifth"],
            class_group=s2["class_a"], status="active", enrolled_on=datetime.date(2027, 2, 1), **_audit(other))
        self._machine(lab, expect=400, enrolment=str(foreign.id))
        self._machine(lab)
        moved = self.tech.post(f"{API}virtuallabs/{lab}/network_mode/", {"mode": "isolated"}, format="json")
        self.assertIn(moved.status_code, (200, 202), moved.content)
        self.assertEqual(self.docker.containers["linux-ana-00007"]["networks"], ["labmgr-linux-ana-00007"])
        self.assertEqual(self.tech.post(f"{API}virtuallabs/{lab}/network_mode/", {"mode": "x"},
                                        format="json").status_code, 400)

    def test_the_legacy_lab_manager_database_is_imported_without_passwords(self):
        path = os.path.join(tempfile.mkdtemp(), "db.sqlite3")
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE labs (id INTEGER PRIMARY KEY, name TEXT, description TEXT, network_name TEXT,
                               network_mode TEXT, created_at TEXT);
            CREATE TABLE machines (id INTEGER PRIMARY KEY, lab_name TEXT, student_username TEXT, container_name TEXT,
                image TEXT, ssh_port INTEGER, http_port INTEGER, https_port INTEGER, ram TEXT, cpus TEXT, status TEXT,
                volume_name TEXT, network_name TEXT, ssh_user TEXT, ssh_password TEXT, created_at TEXT,
                updated_at TEXT, deleted_at TEXT);
            CREATE TABLE history (id INTEGER PRIMARY KEY, action TEXT, container_name TEXT, lab_name TEXT,
                                  student_username TEXT, message TEXT, created_at TEXT);
            INSERT INTO labs VALUES (1, 'linux', '', 'labmgr-linux', 'shared', '2026-11-14 20:00:00');
            INSERT INTO machines VALUES (1, 'linux', 'pedro', 'linux-pedro', 'ubuntu-lab:1', 2202, 8002, 8443,
                '1024m', '1', 'running', 'labmgr-linux-pedro-home', 'labmgr-linux', 'pedro', 'secret123',
                '2026-11-14 20:10:00', NULL, NULL);
            INSERT INTO machines VALUES (2, 'linux', 'metano', 'linux-metano', 'ubuntu-lab:1', 2200, 8000, 8442,
                '1024m', '1', 'deleted', '', 'labmgr-linux', 'metano', 'old', '2026-11-14 20:05:00', NULL,
                '2026-11-14 20:06:00');
            INSERT INTO history VALUES (1, 'create', 'linux-pedro', 'linux', 'pedro', 'Máquina criada',
                                        '2026-11-14 20:10:00');
        """)
        db.commit()
        db.close()
        self.docker.containers["linux-pedro"] = {"running": True, "networks": ["labmgr-linux"], "volume": "",
                                                 "labels": {}, "image": "ubuntu-lab:1"}
        args = ["import-legacy", "--sqlite", path, "--entity", self.tenant["entity"].name,
                "--branch", self.tenant["branch"].name]
        call_command("lab", *args, stdout=io.StringIO())
        call_command("lab", *args, stdout=io.StringIO())                    # idempotent
        self.assertEqual(m.VirtualLab.objects.count(), 1)
        pedro = m.VirtualMachine.objects.get(container_name="linux-pedro")
        self.assertEqual((pedro.status, pedro.ssh_port, pedro.entity_id), ("running", 2202, self.tenant["entity"].id))
        self.assertIsNotNone(m.VirtualMachine.all_objects.get(container_name="linux-metano").removed_at)
        self.assertEqual(AuditLog.objects.filter(action="LAB_LEGACY_CREATE").count(), 1)
        self.assertNotIn("secret123", json.dumps(list(AuditLog.objects.values_list("details", flat=True))))
        out = io.StringIO()
        call_command("lab", "machine", "delete", "linux-pedro", "--dry-run", stdout=out)
        self.assertIn("Preview only", out.getvalue())
        self.assertIn("linux-pedro", self.docker.containers)                 # untouched
