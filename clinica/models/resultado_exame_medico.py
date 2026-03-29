from django.db import models
from django_resaas.core.base.models import BaseModel, TimeModel
from django_resaas.core.utils import upload_path

class ResultadoExameMedico(BaseModel):
    valor = models.CharField(max_length=200, null=True)
    parametro = models.ForeignKey("ParamentroResultadoExameMedico", null=True, on_delete=models.CASCADE)
    exame = models.ForeignKey("ExameMedico", null=True, on_delete=models.CASCADE)
    pedido_exame_medico = models.ForeignKey("PedidoExameMedico", null=True, on_delete=models.CASCADE)

    class Meta:
        permissions = (

        )
        

class FileResultadoMedidoExameMedico(BaseModel):
    pedidoExameMedico = models.ForeignKey("PedidoExameMedico", on_delete=models.CASCADE)
    file = models.FileField(upload_to=upload_path('resultados_exames'), null=True)
    class Meta:
        permissions = (

        )
