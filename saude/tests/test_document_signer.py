"""The PDFs a professional signs carry the name of who created the document
(atestado, relatório, guia de transferência, pedido de exame), and the exam
request's list of exams may continue on the next page instead of leaving the
first page empty."""
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from saude.services.document_edit_policy import author_name


def _user(full_name=None, username="drjoao", person=True):
    return SimpleNamespace(
        person=SimpleNamespace(full_name=full_name) if person else None,
        username=username,
        get_full_name=lambda: "",
    )


def _consulta(full_name):
    return SimpleNamespace(employee=SimpleNamespace(person=SimpleNamespace(full_name=full_name)))


class AuthorNameTests(SimpleTestCase):

    def test_the_creators_person_name(self):
        document = SimpleNamespace(created_by=_user("João Mabunda"), consulta=_consulta("Outro Médico"))

        self.assertEqual(author_name(document), "João Mabunda")

    def test_a_creator_without_person_falls_back_to_the_username(self):
        document = SimpleNamespace(created_by=_user(person=False), consulta=None)

        self.assertEqual(author_name(document), "drjoao")

    def test_without_creator_it_is_the_doctor_of_the_consultation(self):
        document = SimpleNamespace(created_by=None, consulta=_consulta("Ana Cossa"))

        self.assertEqual(author_name(document), "Ana Cossa")

    def test_nothing_known_is_none(self):
        self.assertIsNone(author_name(SimpleNamespace(created_by=None, consulta=None)))


class SignatureLineTests(SimpleTestCase):

    TEMPLATES = (
        "saude/atestadomedico.html",
        "saude/relatoriomedico.html",
        "saude/guiatransferencia.html",
        "saude/pedidoexamemedico.html",
    )

    def test_every_signed_pdf_prints_the_signers_name(self):
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                html = render_to_string(template, {"signer_name": "João Mabunda", "items": []})

                self.assertIn('<strong class="signer-name">João Mabunda</strong>', html)

    def test_without_a_name_the_line_keeps_only_the_role(self):
        for template in self.TEMPLATES:
            with self.subTest(template=template):
                html = render_to_string(template, {"items": []})

                self.assertNotIn("signer-name\">", html)


class ExamRequestPagingTests(SimpleTestCase):

    def test_the_exam_list_is_not_one_unbreakable_box(self):
        html = render_to_string("saude/pedidoexamemedico.html", {"items": []})

        self.assertIn('class="box box--list"', html)
        self.assertIn(".box--list { page-break-inside: auto; }", html)
