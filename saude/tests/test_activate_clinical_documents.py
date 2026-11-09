"""Migration 0019: clinical documents left 'Inactive' (TimeModel's default)
become Active so the right-menu history (state=Active) lists them; result
folders and deleted documents are left as they are."""
import importlib
from datetime import date

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from saude.models.consulta import Consulta
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.receitamedica import ReceitaMedica
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.tests.test_operational_dashboards import _audit, _employee, _patient
from testutils.tenant import bootstrap_tenant

activate = importlib.import_module("saude.migrations.0019_activate_clinical_documents").activate


class ActivateClinicalDocumentsTests(TestCase):

    def test_inactive_documents_become_active_but_not_folders_or_deleted_ones(self):
        tenant = bootstrap_tenant("activate-docs", modules=("saude", "hr"))
        audit = {**_audit(tenant), "state": "Inactive"}
        patient = _patient(tenant, "Rabeca")
        consulta = Consulta.objects.create(paciente=patient, employee=_employee(tenant, tenant["user"].person),
                                           dc="a", **_audit(tenant))
        receita = ReceitaMedica.objects.create(consulta=consulta, **audit)
        pedido = PedidoExameMedico.objects.create(paciente=patient, origin="direct", **audit)
        deleted = PedidoExameMedico.objects.create(paciente=patient, origin="direct", **audit)
        deleted.delete()
        folder = ResultadoExameMedico.objects.create(paciente=patient, nome="Pasta", tipo="Folder", **audit)

        activate(apps, None)

        self.assertEqual(ReceitaMedica.objects.get(pk=receita.pk).state, "Active")
        self.assertEqual(PedidoExameMedico.objects.get(pk=pedido.pk).state, "Active")
        self.assertEqual(PedidoExameMedico.all_objects.get(pk=deleted.pk).state, "Inactive")
        self.assertEqual(ResultadoExameMedico.objects.get(pk=folder.pk).state, "Inactive")
