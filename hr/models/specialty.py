from django.db import models
from django_resaas.saas.core.base.models import BaseModel

class Specialty(BaseModel):
    # =========================
    # 🏷️ CORE FIELDS
    # =========================
    title = models.CharField(max_length=150)  # 🔥 melhor que name
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # what the health PDFs print under the signing doctor's name for this
    # specialty (e.g. "Médico Internista" for Medicina Interna); the title
    # when empty - saude/services/document_signer.signer_role
    signature = models.CharField(max_length=150, null=True, blank=True)

    # =========================
    # 🔐 META
    # =========================
    class Meta:
        permissions = ()
        ordering = ['title']
        unique_together = ('entity', 'title')  # 🔥 aqui

    # =========================
    # ⚙️ RESAAS CONFIG
    # =========================
    class RESAAS:
        label_field = "title"
        search_fields = ["title", "code"]
        crud = True
        routes = {
            'list': "list_specialty",
            'view': "view_specialty",
            'add': "add_specialty",
            'change': "change_specialty"
        }

    # =========================
    # 🧠 STRING REPRESENTATION
    # =========================
    def __str__(self):
        return self.title