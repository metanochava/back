from saude.models.paciente import Paciente
from saude.models.patient_identifier import PatientIdentifier
from saude.models.consent_grant import ConsentGrant
from saude.models.emergency_access import EmergencyAccess
from saude.models.patient_merge import PatientMerge
from saude.models.consulta import Consulta
from saude.models.receitamedica import ReceitaMedica
from saude.models.itemreceita import ItemReceita
from saude.models.atestadomedico import AtestadoMedico
from saude.models.relatoriomedico import RelatorioMedico
from saude.models.clinicalsummary import ClinicalSummary
from saude.models.guiatransferencia import GuiaTransferencia
from saude.models.pedidoexamemedico import PedidoExameMedico
from saude.models.dadovital import DadoVital
from saude.models.examemedico import ExameMedico
from saude.models.classeexamemedico import ClasseExameMedico
from saude.models.favouriteexam import FavouriteExam
from saude.models.examset import ExamSet
from saude.models.tipoexamemedico import TipoExameMedico
from saude.models.medicamento import Medicamento
from saude.models.medicacaocorrente import MedicacaoCorrente
from saude.models.doencacorrente import DoencaCorrente
from saude.models.alergiacorrente import AlergiaCorrente
from saude.models.exam_parameter import ExamParameter
from saude.models.exam_reference_range import ExamReferenceRange
from saude.models.result_parameter_value import ResultParameterValue
from saude.models.appointment_request import AppointmentRequest
from saude.models.clinical_billing import ClinicalBillingRule, ExamMaterialRule, ClinicalCharge, MaterialConsumption
# Every model is registered when the app loads (apps.populate imports this
# package): a model imported only later (e.g. Medico, from a view) misses the
# reverse relations Django has already cached on the related model -
# Employee.medico was then unknown to queries ("Cannot resolve keyword
# 'medico'") depending on which request came first.
from saude.models.agenda import Agenda
from saude.models.alergiamedicamentosa import AlergiaMedicamentosa
from saude.models.cirurgia import Cirurgia
from saude.models.consultorio import Consultorio
from saude.models.diagnostico import Diagnostico
from saude.models.episodioclinico import EpisodioClinico
from saude.models.horariomedico import HorarioMedico
from saude.models.imunizacao import Imunizacao
from saude.models.internamento import Internamento
from saude.models.itempedidoexamemedico import ItemPedidoExameMedico
from saude.models.medico import Medico
from saude.models.observacaoclinica import ObservacaoClinica
from saude.models.procedimento import Procedimento
from saude.models.resultadoexamemedico import ResultadoExameMedico
from saude.models.vacina import Vacina
