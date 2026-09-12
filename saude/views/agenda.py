from datetime import datetime, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from django_resaas.saas.core.base.views import BaseAPIView, registerView
from django_resaas.hr.models.employee import Employee

from saude.models.agenda import Agenda
from saude.serializers.agenda import AgendaSerializer

DEFAULT_DURATION = timedelta(minutes=30)


def _as_datetime(t):
    return datetime.combine(datetime.min, t)


def _effective_end(hora_inicio, hora_fim):
    """hora_fim é opcional no modelo - o próprio diálogo de marcação
    (AgendaConsultaDialog.vue's buildSlots()) já trata uma marcação
    sem hora_fim como ocupando 30 min a partir de hora_inicio para
    efeitos de "horário ocupado"; replicamos aqui a mesma convenção
    para o cálculo de sobreposição ficar consistente com o que o
    utilizador já vê no ecrã."""

    if hora_fim:
        return hora_fim
    return (_as_datetime(hora_inicio) + DEFAULT_DURATION).time()


def _assert_no_overlap(*, medico_id, data, hora_inicio, hora_fim, exclude_id=None):
    """
    Impede duas marcações sobrepostas para o mesmo médico no mesmo
    dia (CLAUDE.md secção 23: "appointment slot allocation" é
    explicitamente listado como caso crítico de concorrência).

    select_for_update() na própria Employee funciona como mutex por
    médico: mesmo quando ainda não existe nenhuma Agenda nesse dia
    (nada para bloquear ainda), duas tentativas concorrentes de
    marcar o MESMO médico serializam-se aqui - fecha a janela de
    corrida que o filtro de "horários ocupados" do frontend, sozinho,
    não fecha (é só uma leitura feita antes de gravar, não uma
    reserva).

    Só exclui marcações "cancelada" (mesmo critério já usado pelo
    frontend) - uma marcação "concluida"/"faltou" no passado continua
    a contar como ocupando esse horário nesse dia, para não introduzir
    uma regra de negócio diferente da que já é mostrada ao utilizador.
    """

    Employee.objects.select_for_update().get(id=medico_id)

    novo_fim = _effective_end(hora_inicio, hora_fim)

    existentes = (
        Agenda.objects
        .select_for_update()
        .filter(medico_id=medico_id, data=data)
        .exclude(estado="cancelada")
    )

    if exclude_id:
        existentes = existentes.exclude(id=exclude_id)

    for outra in existentes:
        outro_fim = _effective_end(outra.hora_inicio, outra.hora_fim)

        if hora_inicio < outro_fim and novo_fim > outra.hora_inicio:
            raise DjangoValidationError(
                "O médico já tem uma marcação entre "
                f"{outra.hora_inicio.strftime('%H:%M')} e "
                f"{outro_fim.strftime('%H:%M')} neste dia."
            )


@registerView("agendas")
class AgendaAPIView(BaseAPIView):

    queryset = Agenda.objects.all()
    serializer_class = AgendaSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        validated = serializer.validated_data

        try:
            _assert_no_overlap(
                medico_id=validated["medico"].id,
                data=validated["data"],
                hora_inicio=validated["hora_inicio"],
                hora_fim=validated.get("hora_fim"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)

        super().perform_create(serializer)

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        validated = serializer.validated_data

        # Só revalida sobreposição se um campo de horário/médico está
        # mesmo a mudar - um PATCH que só altera "estado" (ex.:
        # cancelar) não deve poder ser bloqueado por dados antigos
        # que, por hipótese, já se sobrepusessem antes deste guard
        # existir.
        touches_schedule = any(
            field in validated
            for field in ("medico", "data", "hora_inicio", "hora_fim")
        )

        if touches_schedule:
            medico = validated.get("medico", instance.medico)
            data = validated.get("data", instance.data)
            hora_inicio = validated.get("hora_inicio", instance.hora_inicio)
            hora_fim = validated.get("hora_fim", instance.hora_fim)

            try:
                _assert_no_overlap(
                    medico_id=medico.id,
                    data=data,
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    exclude_id=instance.id,
                )
            except DjangoValidationError as exc:
                raise DRFValidationError(exc.messages)

        super().perform_update(serializer)
