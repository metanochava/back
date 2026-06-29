
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.serializers.resultadoexamemedico import ResultadoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.models.entity import Entity
from django_resaas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode


@registerView('resultadoexamemedicos')
class ResultadoExameMedicoAPIView(BaseAPIView):
    queryset = ResultadoExameMedico.objects.all()   
    serializer_class = ResultadoExameMedicoSerializer


   
    @action(
        detail=True,
        methods=['GET'],
    )
    def pdf(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        pedido = self.get_object()
        paciente = pedido.paciente

        items = (
            pedido.items
            .select_related(
                "exame",
                "exame__classe_exame_medico",
                "exame__classe_exame_medico__tipo_exame_medico",
            )
            .order_by(
                "exame__classe_exame_medico__tipo_exame_medico__ordem",
                "exame__classe_exame_medico__ordem",
                "exame__nome",
            )
        )

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None

        qr_b64 = make_qr_b64(f"{pedido.id}")
        barcode_b64 = make_barcode_b64(f"{pedido.id}")
        
        return PDF(
            "saude/resultadopedidoexamemedico.html",
            request,
            entity=entity,
            pedido=pedido,
            items=items,
            logo_b64=logo_b64,
            qr_b64=make_qr_b64(str(pedido.id)),
            barcode_b64=make_barcode_b64(str(pedido.id)),
            paciente=paciente,
        )

