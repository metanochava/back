from django.db.models import Prefetch

from rest_framework.response import Response

from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from django_resaas.models.entity import Entity

from saude.models.tipoexamemedico import TipoExameMedico
from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.examemedico import ExameMedico


@registerView("catalogoexames")
class CatalogoExameAPIView(BaseAPIView):

    queryset = TipoExameMedico.objects.none()
    serializer_class = None

    pagination_class = None
    filter_backends = []
    ordering_fields = []
    search_fields = []

    http_method_names = ["get"]

    def list(self, request, *args, **kwargs):

        entity = Entity.objects.get(id=request.entity_id)

        search = request.query_params.get("search", "").strip()

        exames_queryset = (
            ExameMedico.objects
            .filter(
                entity=entity,
                ativo=True
            )
            .order_by("nome")
        )

        if search:
            exames_queryset = exames_queryset.filter(
                nome__icontains=search
            )

        classes_queryset = (
            ClasseExameMedico.objects
            .filter(
                entity=entity
            )
            .order_by("nome")
            .prefetch_related(
                Prefetch(
                    "exames",
                    queryset=exames_queryset
                )
            )
        )

        tipos = (
            TipoExameMedico.objects
            .filter(
                entity=entity
            )
            .order_by("nome")
            .prefetch_related(
                Prefetch(
                    "classes_exames",
                    queryset=classes_queryset
                )
            )
        )

        catalogo = []

        for tipo in tipos:

            tipo_json = {

                "id": tipo.id,
                "nome": tipo.nome,
                "descricao": getattr(tipo, "descricao", None),

                "classes": []

            }

            for classe in tipo.classes_exames.all():

                classe_json = {

                    "id": classe.id,
                    "nome": classe.nome,
                    "descricao": getattr(classe, "descricao", None),

                    "exames": []

                }

                for exame in classe.exames.all():

                    classe_json["exames"].append({

                        "id": exame.id,

                        "codigo": exame.codigo,

                        "nome": exame.nome,

                        "descricao": exame.descricao,

                        "ativo": exame.ativo

                    })

                # adiciona SEMPRE a classe,
                # mesmo que não tenha exames
                tipo_json["classes"].append(classe_json)

            # adiciona SEMPRE o tipo,
            # mesmo que não tenha classes
            catalogo.append(tipo_json)

        return Response(catalogo)