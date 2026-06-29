
from django_resaas.core.base.views import BaseAPIView
from django_resaas.core.base.views import registerView
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.serializers.pedidoexamemedico import PedidoExameMedicoSerializer
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.serializers.resultadoexamemedico import ResultadoExameMedicoSerializer
from saude.serializers.itempedidoexamemedico import ItemPedidoExameMedicoSerializer
from rest_framework.decorators import action
from django_resaas.models.entity import Entity
from django_resaas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF, all

from django.db.models import Prefetch
import barcode
import qrcode

from saude.models.consulta import Consulta
from django.utils import timezone
from hr.models.employee import Employee
from saude.models.paciente import Paciente


@registerView('pedidoexamemedicos')
class PedidoExameMedicoAPIView(BaseAPIView):
    queryset = PedidoExameMedico.objects.all()   
    serializer_class = PedidoExameMedicoSerializer

    def create(self, request, *args, **kwargs):

        employee = Employee.objects.get(
            person=request.user.person
        )

        paciente = Paciente.objects.get(
            id=request.data.get("paciente")
        )

        consulta, created = Consulta.objects.get_or_create(
            paciente=paciente,
            employee= employee,
            data=timezone.now().date(),

            entity_id= request.entity_id,
            branch_id =  request.branch_id,
            created_by = request.user,
            updated_by  = request.user,   
        )

        if not created:
            consulta.updated_by = request.user
            consulta.save(update_fields=["updated_by"])


        data = request.data.copy()
        data['consulta'] = consulta.id
        print(data['consulta'])
        serializer = self.get_serializer(
            data=data
        )

        serializer.is_valid(
            raise_exception=True
        )

        pedidoexame = serializer.save(
            consulta=consulta,
            entity=consulta.entity,
            branch=consulta.branch,
            created_by=request.user,
            updated_by=request.user
        )

        return all(request, 
            data= self.get_serializer(pedidoexame).data,
            status=201
        )

   
    @action(
        detail=True,
        methods=['GET'],
    )
    def pdf(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        pedido = self.get_object()
        paciente = pedido.consulta.paciente

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
            "saude/pedidoexamemedico.html",
            request,
            entity=entity,
            pedido=pedido,
            items=items,
            logo_b64=logo_b64,
            qr_b64=make_qr_b64(str(pedido.id)),
            barcode_b64=make_barcode_b64(str(pedido.id)),
            paciente=paciente,
        )





    @action(
        detail=True,
        methods=["get"],
    )
    def items(self, request, *args, **kwargs):

        pedido = self.get_object()

        queryset = (
            pedido.items
            .select_related(
                "pedido",
                "exame",
                "exame__classe_exame_medico",
                "exame__classe_exame_medico__tipo_exame_medico",
            )
            .prefetch_related(
                Prefetch(
                    "resultados",
                    queryset=ResultadoExameMedico.objects.select_related(
                        "emitido_por",
                        "validado_por",
                    ).order_by(
                        "-numero_revisao",
                        "-created_at",
                    ),
                ),
            )
            .order_by(
                "exame__classe_exame_medico__tipo_exame_medico__ordem",
                "exame__classe_exame_medico__ordem",
                "exame__nome",
            )
        )

        serializer = ItemPedidoExameMedicoSerializer(
            queryset,
            many=True,
            context={
                "request": request,
            },
        )

        return all(
            request,
            data=serializer.data,
            status=200,
        )    


        
           
    @action(
        detail=True,
        methods=['GET'],
    )
    def resultados(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        pedido = self.get_object()
        paciente = pedido.consulta.paciente

        resultados = ResultadoExameMedico.objects.filter(
            item_pedido__pedido=pedido
        ).select_related(
            "item_pedido",
            "item_pedido__exame",
            "emitido_por",
            "validado_por"
        )

        return all(
            request,
            data=ResultadoExameMedicoSerializer(resultados, many=True).data,
            status=200
        )
