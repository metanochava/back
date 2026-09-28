"""seed_exam_catalogue: the standard exam catalogue of an Entity
(saude/services/exam_catalogue_service.py, saude/services/catalogos/exam_catalogue.py)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.exam_parameter import ExamParameter, ExamReferenceRange
from saude.models.examemedico import ExameMedico
from saude.models.tipoexamemedico import TipoExameMedico
from saude.services import exam_catalogue_service as service
from saude.services.catalogos.exam_catalogue import CATALOGUE
from testutils.tenant import bootstrap_tenant


def _exams():
    return [e for t in CATALOGUE for c in t["classes"] for e in c["exames"]]


class CatalogueDataTests(TestCase):
    """The data itself, without a database."""

    def test_exam_names_are_unique_in_the_catalogue(self):
        names = [e["nome"] for e in _exams()]
        self.assertEqual(len(names), len(set(names)))

    def test_parameter_codes_are_unique_per_exam(self):
        for exam in _exams():
            codes = [p["code"] for p in exam["params"]]
            self.assertEqual(len(codes), len(set(codes)), exam["nome"])

    def test_no_clinical_reference_value_in_the_catalogue(self):
        for exam in _exams():
            self.assertNotIn("valor_referencia", exam)
            for param in exam["params"]:
                self.assertFalse({"low", "high", "critical_low", "critical_high"} & set(param), exam["nome"])


class SeedExamCatalogueTests(TestCase):

    def setUp(self):
        self.tenant = bootstrap_tenant("exam-catalogue", modules=("saude", "hr"))

    def _seed(self, **kwargs):
        return service.seed(entity=str(self.tenant["entity"].id), **kwargs)

    def test_seeds_the_whole_catalogue_in_the_given_tenant(self):
        report = self._seed()

        entity = self.tenant["entity"]
        self.assertEqual(ExameMedico.objects.filter(entity=entity).count(), len(_exams()))
        self.assertEqual(report.created["exams"], len(_exams()))
        self.assertEqual(ExamParameter.objects.filter(entity=entity).count(),
                         sum(len(e["params"]) for e in _exams()))
        self.assertFalse(ExameMedico.objects.exclude(entity=entity).exists())
        self.assertTrue(all(p.branch_id == self.tenant["branch"].id for p in ExamParameter.objects.all()))

    def test_no_reference_range_is_ever_created(self):
        self._seed()

        self.assertEqual(ExamReferenceRange.objects.count(), 0)

    def test_parameters_are_valid_and_structured(self):
        self._seed()

        cbc = ExameMedico.objects.get(entity=self.tenant["entity"], nome="Hemograma completo")
        hb = cbc.parameters.get(code="hb")
        self.assertEqual((hb.data_type, hb.unit, hb.decimal_places), ("decimal", "g/dL", 1))
        abo = ExameMedico.objects.get(nome="Grupo sanguíneo e factor Rh").parameters.get(code="abo")
        self.assertEqual(abo.choices, ["A", "B", "AB", "O"])
        for param in ExamParameter.objects.all():
            param.full_clean(exclude=["entity", "branch", "created_by", "updated_by"])

    def test_running_twice_creates_nothing_new(self):
        self._seed()
        counts = [M.objects.count() for M in (TipoExameMedico, ClasseExameMedico, ExameMedico, ExamParameter)]

        report = self._seed()

        self.assertEqual(sum(report.created.values()), 0)
        self.assertEqual([M.objects.count() for M in (TipoExameMedico, ClasseExameMedico, ExameMedico, ExamParameter)],
                         counts)

    def test_laboratory_changes_are_kept_and_missing_parameters_added(self):
        self._seed()
        cbc = ExameMedico.objects.get(nome="Hemograma completo")
        hb = cbc.parameters.get(code="hb")
        hb.unit = "g/L"
        hb.save()
        cbc.parameters.filter(code="mpv").delete()
        cbc.ativo = False
        cbc.save()

        report = self._seed()

        cbc.refresh_from_db()
        self.assertFalse(cbc.ativo)
        self.assertEqual(cbc.parameters.get(code="hb").unit, "g/L")
        self.assertEqual(report.created["parameters"], 1)
        self.assertTrue(cbc.parameters.filter(code="mpv").exists())

    def test_an_existing_exam_is_reused_not_duplicated(self):
        tenant = {k: self.tenant[k] for k in ("entity", "branch")}
        tipo = TipoExameMedico.objects.create(nome="Laboratório", **tenant)
        classe = ClasseExameMedico.objects.create(nome="Rotina", tipo_exame_medico=tipo, **tenant)
        own = ExameMedico.objects.create(nome="Hemograma completo", codigo="X-1", classe_exame_medico=classe, **tenant)

        self._seed()

        own.refresh_from_db()
        self.assertEqual(ExameMedico.objects.filter(nome="Hemograma completo").count(), 1)
        self.assertEqual((own.codigo, own.classe_exame_medico_id), ("X-1", classe.id))
        self.assertTrue(own.parameters.filter(code="hb").exists())

    def test_another_entitys_catalogue_is_untouched(self):
        other = bootstrap_tenant("exam-catalogue-other", modules=("saude", "hr"))

        self._seed()

        self.assertFalse(ExameMedico.objects.filter(entity=other["entity"]).exists())

    def test_dry_run_writes_nothing(self):
        report = self._seed(dry_run=True)

        self.assertEqual(report.created["exams"], len(_exams()))
        self.assertEqual(ExameMedico.objects.count(), 0)

    def test_unknown_entity_is_an_error(self):
        with self.assertRaises(service.CatalogueSeedError):
            service.seed(entity="No such entity")

    def test_command(self):
        out = StringIO()

        call_command("seed_exam_catalogue", "--entity", str(self.tenant["entity"].id), stdout=out)

        self.assertIn("created", out.getvalue())
        self.assertEqual(ExameMedico.objects.count(), len(_exams()))
