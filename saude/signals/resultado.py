from django.db.models.signals import post_save
from django.dispatch import receiver

from saude.models.paciente import Paciente
from saude.models.resultadoexamemedico import ResultadoExameMedico


PASTAS_INICIAIS = [

    "Laboratório",
    "Hematologia",
    "Bioquímica",
    "Microbiologia",
    "Parasitologia",
    "Imagiologia",
    "RX",
    "Ecografia",
    "TAC",
    "Ressonância Magnética",
    "Cardiologia",
    "Endoscopia",
    "Outros"

]


@receiver(post_save, sender=Paciente)
def criar_pastas_paciente(sender, instance, created, **kwargs):

    # if not created:
    #     return

    raiz = ResultadoExameMedico.objects.create(

        paciente=instance,

        nome="Resultados de Exames",

        tipo="Folder",

        entity=instance.entity,
        branch=instance.branch,
        created_by=instance.created_by,
        updated_by=instance.updated_by,

    )

    for nome in PASTAS_INICIAIS:

        ResultadoExameMedico.objects.create(

            paciente=instance,

            pai=raiz,

            nome=nome,

            tipo="Folder",

            entity=instance.entity,
            branch=instance.branch,
            created_by=instance.created_by,
            updated_by=instance.updated_by,

        )