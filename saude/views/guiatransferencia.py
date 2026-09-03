
from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView
from saude.models.guiatransferencia import GuiaTransferencia
from saude.serializers.guiatransferencia import GuiaTransferenciaSerializer
from rest_framework.decorators import action
from django_resaas.engine.models.entity import Entity
from django_resaas.engine.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF, all

import barcode
import qrcode


from saude.models.consulta import Consulta
from django.utils import timezone
from django_resaas.hr.models.employee import Employee
from saude.models.paciente import Paciente



@registerView('guiatransferencias')
class GuiaTransferenciaAPIView(BaseAPIView):
    queryset = GuiaTransferencia.objects.all()   
    serializer_class = GuiaTransferenciaSerializer


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

        receita = serializer.save(
            consulta=consulta,
            entity=consulta.entity,
            branch=consulta.branch,
            created_by=request.user,
            updated_by=request.user
        )

        return all(request, 
            data= self.get_serializer(receita).data,
            status=201
        )
    

    @action(
        detail=True,
        methods=['GET'],
    )
    def pdf(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)
        guiatransferencia = self.get_object()

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None

        qr_b64 = make_qr_b64(f"{guiatransferencia.id}")
        barcode_b64 = make_barcode_b64(f"{guiatransferencia.id}")
        
        return PDF("saude/guiatransferencia.html", request, 
            entity=entity,
            logo_b64=logo_b64,
            qr_b64=qr_b64,
            barcode_b64=barcode_b64,
            guiatransferencia=guiatransferencia
        )
