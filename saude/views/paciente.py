from django.utils import timezone

from rest_framework.decorators import action

from django_resaas.core.base.views import (
    BaseAPIView,
    registerView,
)

from django_resaas.core.utils import (
    PDF,
    make_barcode_b64,
    make_qr_b64,
    png_bytes_to_b64,
)

from django_resaas.models.entity import Entity

from django_resaas.data.user.serializers.user import UserSerializer

from saude.models.paciente import Paciente
from saude.serializers.paciente import PacienteSerializer


@registerView("pacientes")
class PacienteAPIView(BaseAPIView):

    queryset = Paciente.objects.all()

    serializer_class = PacienteSerializer

    @action(
        detail=True,
        methods=["GET"],
    )
    def pdf(self, request, *args, **kwargs):

        paciente = self.get_object()

        entity = paciente.entity

        ####################################################
        # LOGO
        ####################################################

        logo_b64 = None

        try:

            if entity.logo and entity.logo.path:

                with open(entity.logo.path, "rb") as f:

                    logo_b64 = png_bytes_to_b64(
                        f.read()
                    )

        except Exception:

            logo_b64 = None

        ####################################################
        # QR CODE
        ####################################################

        qr_b64 = make_qr_b64(

            str(paciente.id)

        )

        ####################################################
        # BARCODE
        ####################################################

        barcode_b64 = make_barcode_b64(

            str(
                paciente.nid
                or paciente.id
            )

        )

        ####################################################
        # FOTO DO PACIENTE
        ####################################################

        user = getattr(

            paciente.person,

            "user",

            None,

        )

        profile = None

        profile_b64 = None

        if user:

            serializer = UserSerializer(

                user,

                context={

                    "request": request,

                    "include_fields": [

                        "profile"

                    ],

                }

            )

            profile = serializer.data.get(

                "profile"

            )

            try:

                if (

                    getattr(
                        user,
                        "profile",
                        None
                    )

                    and

                    user.profile.path

                ):

                    with open(

                        user.profile.path,

                        "rb",

                    ) as f:

                        profile_b64 = png_bytes_to_b64(

                            f.read()

                        )

            except Exception:

                profile_b64 = None


                ####################################################
        # PDF
        ####################################################

        return PDF(

            "saude/paciente.html",

            request,

            entity=entity,

            paciente=paciente,

            #
            # Logo da instituição
            #
            logo_b64=logo_b64,

            #
            # Foto do paciente
            #
            profile=profile,

            profile_b64=profile_b64,

            #
            # QR Code
            #
            qr_b64=qr_b64,

            #
            # Código de barras
            #
            barcode_b64=barcode_b64,

            #
            # Data de emissão
            #
            data_emissao=timezone.now().date(),

        )