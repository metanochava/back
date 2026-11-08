"""Medication names are stored and printed in capitals (Medicamento.save(),
receitamedica.html)."""
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import TestCase

from saude.models.medicamento import Medicamento
from saude.tests.test_operational_dashboards import _audit
from testutils.tenant import bootstrap_tenant


class MedicamentoUppercaseTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("med-upper", modules=("saude",))

    def test_saved_in_capitals(self):
        med = Medicamento.objects.create(descricao=" Paracetamol 500mg ", principio_ativo="paracetamol", **_audit(self.tenant))
        med.refresh_from_db()
        self.assertEqual(med.descricao, "PARACETAMOL 500MG")
        self.assertEqual(med.principio_ativo, "PARACETAMOL")

    def test_edit_keeps_capitals(self):
        med = Medicamento.objects.create(descricao="X", **_audit(self.tenant))
        med.descricao = "amoxicilina"
        med.save()
        med.refresh_from_db()
        self.assertEqual(med.descricao, "AMOXICILINA")

    def test_prescription_prints_capitals(self):
        item = SimpleNamespace(medicamento=SimpleNamespace(descricao="ibuprofeno"), dosagem="", quantidade="", observacao="")
        html = render_to_string("saude/receitamedica.html", {"items": [item], "labels": {}, "entity": SimpleNamespace(name="Amal")})
        self.assertIn("IBUPROFENO", html)
