from django.db.models import Q

from rest_framework.decorators import action
from rest_framework.response import Response

from django_resaas.saas.core.decorators.action import resaas_action
from django_resaas.saas.core.base.permissions import isPermited
from django_resaas.saas.core.exceptions import ResaasAPIException
from rest_framework import status
from saude.services import exam_request_service, lab_result_service
from saude.models.paciente import Paciente

from django_resaas.saas.core.base.views import (
    BaseAPIView,
    registerView,
)

from django_resaas.saas.models.entity import Entity

from django_resaas.saas.core.utils import (
    PDF,
    all,
    make_barcode_b64,
    make_qr_b64,
    png_bytes_to_b64,
)

from saude.models.resultadoexamemedico import (
    ResultadoExameMedico,
)

from saude.serializers.resultadoexamemedico import (
    ResultadoExameMedicoSerializer,
)


@registerView("resultadoexamemedicos")
class ResultadoExameMedicoAPIView(BaseAPIView):

    queryset = (
        ResultadoExameMedico.objects
        .select_related(
            "pai",
            "paciente",
            "item_pedido",
            "emitido_por",
            "validado_por",
        )
    )

    serializer_class = ResultadoExameMedicoSerializer

    ##########################################################
    # CREATE
    ##########################################################

    def perform_create(self, serializer):

        # validating needs its own permission; validation metadata is the
        # server's (exam_request_service.enforce_result_write)
        exam_request_service.enforce_result_write(self.request, serializer.validated_data)

        serializer.save(

            entity_id=self.request.entity_id,

            branch_id=self.request.branch_id,

            created_by=self.request.user,

            updated_by=self.request.user,

            emitido_por=self.request.user,

        )

    ##########################################################
    # UPDATE
    ##########################################################

    def perform_update(self, serializer):

        # a validated result is never silently overwritten (409)
        exam_request_service.enforce_result_write(
            self.request, serializer.validated_data, instance=serializer.instance
        )

        serializer.save(

            updated_by=self.request.user,

        )

    ##########################################################
    # VALIDATE
    ##########################################################

    @resaas_action(detail=True, methods=["post"], label="Validate", icon="verified")
    def validate(self, request, *args, **kwargs):
        """Clinical validation of a result - needs
        validate_resultadoexamemedico (recording a result does not)."""

        result = exam_request_service.validate_result(request, self.get_object())
        return Response(self.get_serializer(result).data)

    @resaas_action(detail=True, methods=["post"], label="Release", icon="publish")
    def release(self, request, *args, **kwargs):
        """Makes a validated result available to the requester and the
        patient - release_resultadoexamemedico (validating does not)."""
        result = lab_result_service.release_result(request, self.get_object())
        return Response(self.get_serializer(result).data)

    @resaas_action(detail=True, methods=["post"], label="Amend", icon="history_edu")
    def amend(self, request, *args, **kwargs):
        """Correction of a validated result: a new revision ({"reason"}),
        the validated one stays unchanged."""
        revision = lab_result_service.amend_result(request, self.get_object(), request.data.get("reason"))
        return Response(self.get_serializer(revision).data, status=201)

    ##########################################################
    # EXPLORER
    ##########################################################

    # The results explorer (folders and files of results). GET lists them:
    # list_resultadoexamemedico; POST creates a folder / file: also
    # add_resultadoexamemedico (checked below). A plain @action had no
    # permission, so BaseAPIView refused both to everyone but Root.
    @resaas_action(detail=False, methods=["GET", "POST"], label="Results explorer", icon="folder",
                   permission="list_resultadoexamemedico", visible=False)
    def explorer(self, request):

        # The explorer is always ONE patient's results: `paciente` (query on
        # GET, body on POST) is required and must be a patient of the caller's
        # Entity - never the results of every patient.
        paciente = (request.GET.get("paciente") if request.method == "GET" else request.data.get("paciente"))
        if not paciente:
            raise ResaasAPIException(
                "The patient is required.", code="patient_required",
                details={"paciente": ["This field is required."]}, status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not Paciente.objects.filter(id=paciente, entity_id=request.entity_id).exists():
            raise ResaasAPIException(
                "Patient not found.", code="patient_not_found", status_code=status.HTTP_404_NOT_FOUND,
            )

        ##################################################
        # LISTAGEM
        ##################################################

        if request.method == "GET":

            pai = request.GET.get("pai")

            if pai in ("", "null", "None", None):
                pai = None

            search = request.GET.get("search")

            queryset = ResultadoExameMedico.objects.filter(

                entity_id=request.entity_id,

                branch_id=request.branch_id,

                na_lixeira=False,

            )

            if paciente:

                queryset = queryset.filter(

                    paciente_id=paciente

                )

            ##################################################
            # PESQUISA
            ##################################################

            if search:

                queryset = queryset.filter(

                    Q(nome__icontains=search)

                    |

                    Q(valor_resultado__icontains=search)

                    |

                    Q(observacao__icontains=search)

                    |

                    Q(laudo__icontains=search)

                )

            ##################################################
            # CONTEÚDO DA PASTA
            ##################################################

            else:

                if pai is None:

                    queryset = queryset.filter(
                        pai__isnull=True
                    )

                else:

                    queryset = queryset.filter(
                        pai_id=pai
                    )

            queryset = (

                queryset

                .select_related(

                    "pai",

                    "paciente",

                    "item_pedido",

                )

                .order_by(

                    "-tipo",

                    "nome",

                )

            )

            serializer = self.get_serializer(

                queryset,

                many=True,

            )

            return all(

                request,

                data=serializer.data,

            )

        ##################################################
        # CRIAR PASTA / FICHEIRO
        ##################################################

        if not isPermited(request=request, role="add_resultadoexamemedico"):
            raise ResaasAPIException(
                "Permission denied", code="permission_denied", status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(

            data=request.data

        )

        serializer.is_valid(

            raise_exception=True

        )

        # a folder inside another patient's folder is refused (the tree is per patient)
        pai = serializer.validated_data.get("pai")
        if pai is not None and str(pai.paciente_id) != str(paciente):
            raise ResaasAPIException(
                "The folder belongs to another patient.", code="folder_of_another_patient",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        resultado = serializer.save(

            paciente_id=paciente,
            entity_id=request.entity_id,

            branch_id=request.branch_id,

            created_by=request.user,

            updated_by=request.user,

            emitido_por=request.user,

        )

        return all(

            request,

            data=self.get_serializer(resultado).data,

            status=201,

        )

        ##########################################################
    # RENOMEAR
    ##########################################################

    # Rename: change_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["PATCH"], label="Rename", permission="change_resultadoexamemedico", visible=False)
    def rename(self, request, *args, **kwargs):

        obj = self.get_object()

        nome = request.data.get("nome")

        if not nome:

            return all(
                request,
                message="Informe o novo nome.",
                status=400,
            )

        obj.nome = nome

        obj.updated_by = request.user

        obj.save(
            update_fields=[
                "nome",
                "updated_by",
            ]
        )

        return all(

            request,

            data=self.get_serializer(obj).data,

        )

    ##########################################################
    # MOVER
    ##########################################################

    # Move: change_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["PATCH"], label="Move", permission="change_resultadoexamemedico", visible=False)
    def move(self, request, *args, **kwargs):

        obj = self.get_object()

        destino = None

        if request.data.get("pai"):

            try:

                destino = ResultadoExameMedico.objects.get(

                    pk=request.data["pai"],

                    entity_id=request.entity_id,

                    branch_id=request.branch_id,

                    na_lixeira=False,

                )

            except ResultadoExameMedico.DoesNotExist:

                return all(

                    request,

                    message="Pasta de destino não encontrada.",

                    status=404,

                )

            if destino.tipo != ResultadoExameMedico.FOLDER:

                return all(

                    request,

                    message="O destino deve ser uma pasta.",

                    status=400,

                )

            #
            # impedir mover para si próprio
            #

            if destino.id == obj.id:

                return all(

                    request,

                    message="Destino inválido.",

                    status=400,

                )

        obj.pai = destino

        obj.updated_by = request.user

        obj.save(

            update_fields=[

                "pai",

                "updated_by",

            ]

        )

        return all(

            request,

            data=self.get_serializer(obj).data,

        )

    ##########################################################
    # ENVIAR PARA LIXEIRA
    ##########################################################

    # Delete: delete_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["DELETE"], label="Delete", permission="delete_resultadoexamemedico", visible=False)
    def delete(self, request, *args, **kwargs):

        obj = self.get_object()

        #
        # não apagar pasta com conteúdo
        #

        if obj.is_folder and obj.has_children:

            return all(

                request,

                message="A pasta contém ficheiros ou subpastas.",

                status=400,

            )

        obj.na_lixeira = True

        obj.updated_by = request.user

        obj.save(

            update_fields=[

                "na_lixeira",

                "updated_by",

            ]

        )

        return all(

            request,

            message="Movido para a lixeira.",

        )

    ##########################################################
    # BREADCRUMB
    ##########################################################

    # Breadcrumb: view_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["GET"], label="Breadcrumb", permission="view_resultadoexamemedico", visible=False)
    def breadcrumb(self, request, *args, **kwargs):

        pasta = self.get_object()

        caminho = []

        while pasta:

            caminho.insert(

                0,

                {

                    "id": pasta.id,

                    "nome": pasta.nome,

                    "tipo": pasta.tipo,

                }

            )

            pasta = pasta.pai

        return all(

            request,

            data=caminho,

        )


        ##########################################################
    # PDF
    ##########################################################

    @action(
        detail=True,
        methods=["GET"],
    )
    def pdf(self, request, *args, **kwargs):

        resultado = self.get_object()

        entity = resultado.entity

        logo_b64 = None

        try:

            if entity.logo and entity.logo.path:

                with open(entity.logo.path, "rb") as f:

                    logo_b64 = png_bytes_to_b64(
                        f.read()
                    )

        except FileNotFoundError:
            pass

        return PDF(

            "saude/resultadopedidoexamemedico.html",

            request,

            entity=entity,

            logo_b64=logo_b64,

            # the result itself (the template used to be a copy of the exam
            # request's and showed no result): lab_result_service.pdf_context
            **lab_result_service.pdf_context(request, resultado),

            qr_b64=make_qr_b64(
                str(resultado.id)
            ),

            barcode_b64=make_barcode_b64(
                str(resultado.id)
            ),

        )

    ##########################################################
    # FAVORITO
    ##########################################################

    # Favourite: change_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["PATCH"], label="Favourite", permission="change_resultadoexamemedico", visible=False)
    def favorite(self, request, *args, **kwargs):

        obj = self.get_object()

        obj.favorito = not obj.favorito

        obj.updated_by = request.user

        obj.save(

            update_fields=[

                "favorito",

                "updated_by",

            ]

        )

        return all(

            request,

            data=self.get_serializer(obj).data,

        )

    ##########################################################
    # RESTAURAR DA LIXEIRA
    ##########################################################

    @action(
        detail=True,
        methods=["PATCH"],
    )
    def restore(self, request, *args, **kwargs):

        obj = self.get_object()

        obj.na_lixeira = False

        obj.updated_by = request.user

        obj.save(

            update_fields=[

                "na_lixeira",

                "updated_by",

            ]

        )

        return all(

            request,

            data=self.get_serializer(obj).data,

        )

    ##########################################################
    # LIXEIRA
    ##########################################################

    # Trash: list_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=False, methods=["GET"], label="Trash", permission="list_resultadoexamemedico", visible=False)
    def trash(self, request):

        queryset = (

            ResultadoExameMedico.objects

            .filter(

                entity_id=request.entity_id,

                branch_id=request.branch_id,

                na_lixeira=True,

            )

            .select_related(

                "pai",

                "paciente",

                "item_pedido",

            )

            .order_by(

                "-tipo",

                "nome",

            )

        )

        serializer = self.get_serializer(

            queryset,

            many=True,

        )

        return all(

            request,

            data=serializer.data,

        )

        ##########################################################
    # DOWNLOAD
    ##########################################################

    # Download: view_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["GET"], label="Download", permission="view_resultadoexamemedico", visible=False)
    def download(self, request, *args, **kwargs):

        resultado = self.get_object()

        if resultado.is_folder:

            return all(

                request,

                message="Pastas não podem ser descarregadas.",

                status=400,

            )

        if not resultado.file:

            return all(

                request,

                message="Ficheiro inexistente.",

                status=404,

            )

        return all(

            request,

            data={

                "id": resultado.id,

                "nome": resultado.nome,

                "url": resultado.file.url,

                "mime_type": resultado.mime_type,

                "extensao": resultado.extensao,

                "tamanho": resultado.tamanho,

                "icon": resultado.icon,

                "is_folder": resultado.is_folder,

                "is_file": resultado.is_file,

                "favorito": resultado.favorito,

            },

        )

    ##########################################################
    # PREVIEW
    ##########################################################

    # Preview: view_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["GET"], label="Preview", permission="view_resultadoexamemedico", visible=False)
    def preview(self, request, *args, **kwargs):

        resultado = self.get_object()

        if resultado.is_folder:

            return all(

                request,

                message="Pastas não possuem visualização.",

                status=400,

            )

        if not resultado.file:

            return all(

                request,

                message="Ficheiro inexistente.",

                status=404,

            )

        return all(

            request,

            data={

                "url": resultado.file.url,

                "mime_type": resultado.mime_type,

                "nome": resultado.nome,

            },

        )

    ##########################################################
    # INFO
    ##########################################################

    # Information: view_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=True, methods=["GET"], label="Information", permission="view_resultadoexamemedico", visible=False)
    def info(self, request, *args, **kwargs):

        obj = self.get_object()

        data = self.get_serializer(obj).data

        data.update({

            "icon": obj.icon,

            "is_folder": obj.is_folder,

            "is_file": obj.is_file,

            "children_count": obj.children_count,

            "has_children": obj.has_children,

            "filename": obj.filename,

            "extension": obj.extension,

        })

        return all(

            request,

            data=data,

        )

    ##########################################################
    # FAVORITOS
    ##########################################################

    # Favourites: list_resultadoexamemedico (a plain @action had no permission:
    # BaseAPIView refused it to everyone but Root)
    @resaas_action(detail=False, methods=["GET"], label="Favourites", permission="list_resultadoexamemedico", visible=False)
    def favorites(self, request):

        queryset = (

            ResultadoExameMedico.objects

            .filter(

                entity_id=request.entity_id,

                branch_id=request.branch_id,

                favorito=True,

                na_lixeira=False,

            )

            .select_related(

                "pai",

                "paciente",

                "item_pedido",

            )

            .order_by(

                "-tipo",

                "nome",

            )

        )

        serializer = self.get_serializer(

            queryset,

            many=True,

        )

        return all(

            request,

            data=serializer.data,

        )