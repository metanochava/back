
from django_resaas.saas.core.base.views import BaseAPIView
from saude.services.document_edit_policy import DocumentEditWindowMixin
from django_resaas.saas.core.base.views import registerView
from saude.models.receitamedica import ReceitaMedica
from saude.models.itemreceita import ItemReceita
from saude.serializers.receitamedica import ReceitaMedicaSerializer
from rest_framework.decorators import action
from django_resaas.saas.models.entity import Entity
from django_resaas.saas.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF, all

import barcode
import qrcode

from saude.services import prescription_service



 

 
@registerView('receitamedicas')
# edited only by its author, within 24 h (document_edit_policy)
class ReceitaMedicaAPIView(DocumentEditWindowMixin, BaseAPIView):
    queryset = ReceitaMedica.objects.all()   
    serializer_class = ReceitaMedicaSerializer
    

    # POST receitamedicas/ {paciente, consulta?}: the prescription belongs to a
    # consultation of TODAY of this patient (prescription_service): never a
    # consultation created here, never a patient of another Entity.
    def create(self, request, *args, **kwargs):

        _patient, _professional, consulta = prescription_service.resolve_consultation(
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
        receita = self.get_object()

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None

        # the codes identify THIS prescription (they used to carry the Entity id)
        qr_b64 = make_qr_b64(f"receita:{receita.id}")
        barcode_b64 = make_barcode_b64(str(receita.id).split("-")[0].upper())

        return PDF(
            "saude/receitamedica.html", request,
            entity=entity, logo_b64=logo_b64, qr_b64=qr_b64, barcode_b64=barcode_b64,
            **prescription_service.pdf_context(request, receita),
        )
