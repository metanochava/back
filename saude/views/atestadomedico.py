
from django_resaas.saas.core.base.views import BaseAPIView
from saude.services.document_edit_policy import DocumentEditWindowMixin
from django_resaas.saas.core.base.views import registerView
from saude.services import consultation_service
from saude.models.atestadomedico import AtestadoMedico
from saude.serializers.atestadomedico import AtestadoMedicoSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF, all

import barcode
import qrcode




@registerView('atestadomedicos')
# edited only by its author, within 24 h (document_edit_policy)
class AtestadoMedicoAPIView(DocumentEditWindowMixin, BaseAPIView):
    queryset = AtestadoMedico.objects.all()   
    serializer_class = AtestadoMedicoSerializer

    def create(self, request, *args, **kwargs):

        # the document belongs to a consultation of TODAY of this patient
        # (consultation_service.resolve_for_document): never one created here,
        # never a patient of another Entity
        _patient, _professional, consulta = consultation_service.resolve_for_document(
            request, request.data.get("paciente"), request.data.get("consulta")
        )

        data = request.data.copy()
        data['consulta'] = consulta.id
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
        atestado = self.get_object()

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None

        qr_b64 = make_qr_b64(f"{atestado.id}")
        barcode_b64 = make_barcode_b64(f"{atestado.id}")
        
        return PDF("saude/atestadomedico.html", request, 
            entity=entity,
            logo_b64=logo_b64,
            qr_b64=qr_b64,
            barcode_b64=barcode_b64,
            atestado=atestado
        )
