
from django_resaas.engine.core.base.views import BaseAPIView
from django_resaas.engine.core.base.views import registerView
from saude.models.dadovital import DadoVital
from saude.serializers.dadovital import DadoVitalSerializer
from rest_framework.decorators import action
from django_resaas.engine.models.entity import Entity
from django_resaas.engine.core.utils import make_qr_b64, make_barcode_b64, png_bytes_to_b64, PDF

import barcode
import qrcode


@registerView('dadovitals')
class DadoVitalAPIView(BaseAPIView):
    queryset = DadoVital.objects.all()   
    serializer_class = DadoVitalSerializer
    


    @action(
        detail=True,
        methods=['GET'],
    )
    def pdf(self, request, *args, **kwargs):
        entity = Entity.objects.get(id=self.get_object().entity.id)

        # Normalmente você busca no DB
        # invoice = Invoice.objects.get(id=invoice_id)
        # Exemplo de dados (substituir por dados reais)
    

        customer = {
            "name": "Cliente Exemplo",
            "nif": "4000000000",
            "address": "Rua Y, Benguela, Angola",
            "email": "cliente@email.com",
            "phone": "+244 999 999 999",
        }

        doc = {
            "type": "FATURA",
            "number": "FT 2026/000123",
            "date": "2026-02-05",
            "due_date": "2026-02-10",
            "currency": "AOA",
            "payment_method": "Transferência",
            "reference": "REF-001",
            "notes": "Obrigado pela preferência.",
        }

        lines = [
            {"name":"Produto A", "sku":"A-001", "note":"", "qty":2, "unit_price":"10.000,00", "vat_rate":14, "total":"22.800,00"},
            {"name":"Serviço B", "sku":"S-100", "note":"Mensal", "qty":1, "unit_price":"50.000,00", "vat_rate":14, "total":"57.000,00"},
            {"name":"Serviço B", "sku":"S-100", "note":"Mensal", "qty":1, "unit_price":"50.000,00", "vat_rate":14, "total":"57.000,00"},
        ]

        totals = {
            "subtotal": "60.000,00",
            "vat_total": "8.400,00",
            "discount_total": "0,00",
            "grand_total": "68.400,00",
        }

        logo_b64 = None
        try:
            if entity.logo and entity.logo.path:
                with open(entity.logo.path, "rb") as f:
                    logo_b64 = png_bytes_to_b64(f.read())

        except FileNotFoundError:
            logo_b64 = None



        qr_b64 = make_qr_b64(f"{doc['type']}|{doc['number']}|TOTAL:{totals['grand_total']}")
        barcode_b64 = make_barcode_b64(doc["number"])
        

        return PDF("saude/dadovital.html", request,  entity= entity, customer= customer, doc= doc, lines= lines, totals= totals, logo_b64= logo_b64, qr_b64= qr_b64, barcode_b64= barcode_b64,)
