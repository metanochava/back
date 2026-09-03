from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from django_resaas.engine.core.base.views import BaseAPIView, registerView
from django_resaas.engine.core.decorators import resaas_action
from django_resaas.engine.core.utils import (
    PDF,
    all,
    make_barcode_b64,
    make_qr_b64,
    png_bytes_to_b64,
)
from django_resaas.engine.data.user.serializers.user import UserSerializer

from saude.models.paciente import Paciente
from saude.serializers.paciente import PacienteSerializer


def generate_nid():
    year = timezone.now().strftime("%Y")
    last = Paciente.objects.filter(
        nid__startswith=f"PAC-{year}"
    ).order_by("-nid").first()

    number = int(last.nid.split("-")[-1]) + 1 if last else 1
    return f"PAC-{year}-{number:06d}"


@registerView("pacientes")
class PacienteAPIView(BaseAPIView):
    queryset = Paciente.objects.all()
    serializer_class = PacienteSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data["nid"] = generate_nid()
        data["state"] = "Active"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        paciente = serializer.save(
            entity_id=request.entity_id,
            branch_id=request.branch_id,
            created_by=request.user,
            updated_by=request.user,
        )

        return all(
            request,
            data=self.get_serializer(paciente).data,
            status=201,
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, *args, **kwargs):
        paciente = self.get_object()
        entity = paciente.entity

        logo_b64 = self.file_to_b64(
            getattr(entity, "logo", None)
        )

        user = getattr(paciente.person, "user", None)
        profile = None
        profile_b64 = None

        if user:
            profile = UserSerializer(
                user,
                context={
                    "request": request,
                    "include_fields": ["profile"],
                },
            ).data.get("profile")

            profile_b64 = self.file_to_b64(
                getattr(user, "profile", None)
            )

        return PDF(
            "saude/paciente.html",
            request,
            entity=entity,
            paciente=paciente,
            logo_b64=logo_b64,
            profile=profile,
            profile_b64=profile_b64,
            qr_b64=make_qr_b64(str(paciente.id)),
            barcode_b64=make_barcode_b64(
                str(paciente.nid or paciente.id)
            ),
            data_emissao=timezone.now().date(),
        )

    @staticmethod
    def file_to_b64(file):
        try:
            if file and file.path:
                with open(file.path, "rb") as content:
                    return png_bytes_to_b64(content.read())
        except Exception:
            pass

        return None

    def get_pdflist_context(self, request, queryset):
        context = super().get_pdflist_context(request, queryset)
        context.update({
            "titulo": "Lista de Pacientes",
            "pacientes": queryset,
        })
        return context

    # @resaas_action(
    #     methods=["post"],
    #     detail=True,
    #     label="Test Action",
    #     icon="event",
    #     tooltip="Test RESAAS action",
    #     position="r",
    #     order=10,
    #     visible=True,
    # )
    # def test_action(self, request, pk=None):
    #     return Response({"success": True})

    # @resaas_action(
    #     methods=["post"],
    #     detail=False,
    #     label="Action",
    #     icon="science",
    #     tooltip="Test action",
    #     position="t",
    #     order=10,
    #     visible=True,
    #     autorequest=True,
    # )
    # def pdf_post(self, request, pk=None):
    #     return Response({"Post": True})

    # @resaas_action(
    #     methods=["post"],
    #     detail=False,
    #     label="Mais",
    #     icon="event",
    #     tooltip="Test RESAAS action",
    #     position="t",
    #     order=10,
    #     visible=True,
    #     autorequest=True,
    # )
    # def pdf_up(self, request, pk=None):
    #     return Response({"Mais": True})

    # @resaas_action(
    #     methods=["get"],
    #     detail=True,
    #     label="Test Action",
    #     icon="science",
    #     tooltip="Test RESAAS action",
    #     position="l",
    #     order=10,
    # )
    # def pdf_get(self, request, pk=None):
    #     return Response({"success get": True})

    # @resaas_action(
    #     methods=["get"],
    #     detail=True,
    #     label="Menu",
    #     icon="science",
    #     tooltip="Test RESAAS action",
    #     position="M",
    #     order=10,
    # )
    # def pdf_getk(self, request, pk=None):
    #     return Response({"success get": True})