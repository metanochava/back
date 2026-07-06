from django.db.models import Q

from rest_framework.decorators import action

from django_resaas.core.base.views import (
    BaseAPIView,
    registerView,
)

from django_resaas.models.entity import Entity

from django_resaas.core.utils import (
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

        serializer.save(

            updated_by=self.request.user,

        )

    ##########################################################
    # EXPLORER
    ##########################################################

    @action(
        detail=False,
        methods=["GET", "POST"],
    )
    def explorer(self, request):

        ##################################################
        # LISTAGEM
        ##################################################

        if request.method == "GET":

            paciente = request.GET.get("paciente")

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

        serializer = self.get_serializer(

            data=request.data

        )

        serializer.is_valid(

            raise_exception=True

        )

        resultado = serializer.save(

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

    @action(
        detail=True,
        methods=["PATCH"],
    )
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

    @action(
        detail=True,
        methods=["PATCH"],
    )
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

    @action(
        detail=True,
        methods=["DELETE"],
    )
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

    @action(
        detail=True,
        methods=["GET"],
    )
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

            resultado=resultado,

            paciente=resultado.paciente,

            logo_b64=logo_b64,

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

    @action(
        detail=True,
        methods=["PATCH"],
    )
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

    @action(
        detail=False,
        methods=["GET"],
    )
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

    @action(
        detail=True,
        methods=["GET"],
    )
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

    @action(
        detail=True,
        methods=["GET"],
    )
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

    @action(
        detail=True,
        methods=["GET"],
    )
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

    @action(
        detail=False,
        methods=["GET"],
    )
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