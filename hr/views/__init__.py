# hr/views/__init__.py
#
# Importing every view module here runs their @registerView decorators,
# which populate VIEW_REGISTRY. Without this, only view modules imported
# elsewhere (e.g. by hr/urls.py) ever register, so build_saas_urls()
# silently skips the rest of hr's resources.

from .employee import EmployeeAPIView
from .department import DepartmentAPIView
from .job_position import JobPositionAPIView
from .job_grade import JobGradeAPIView
from .contract import ContractAPIView

from .specialty import SpecialtyAPIView
from .employee_specialty import EmployeeSpecialtyAPIView

from .shift import ShiftAPIView
from .employee_shift import EmployeeShiftAPIView
from .shift_schedule import ShiftScheduleAPIView
from .attendance import AttendanceAPIView
from .holiday import HolidayAPIView

from .salary_component import SalaryComponentAPIView
from .employee_salary import EmployeeSalaryAPIView
from .employee_salary_component import EmployeeSalaryComponentAPIView

from .payroll_period import PayrollPeriodAPIView
from .payroll import PayrollAPIView
from .payroll_item import PayrollItemAPIView

from .payslip import PayslipAPIView

from .leave_type import LeaveTypeAPIView
from .leave_request import LeaveRequestAPIView
from .leave_balance_entry import LeaveBalanceEntryAPIView

from .job_opening import JobOpeningAPIView
from .candidate import CandidateAPIView
from .application import ApplicationAPIView
from .interview import InterviewAPIView

from .onboarding_template import OnboardingTemplateAPIView
from .onboarding_template_task import OnboardingTemplateTaskAPIView
from .employee_onboarding import EmployeeOnboardingAPIView
from .employee_onboarding_task import EmployeeOnboardingTaskAPIView

from .performance_cycle import PerformanceCycleAPIView
from .competency import CompetencyAPIView
from .employee_goal import EmployeeGoalAPIView
from .performance_review import PerformanceReviewAPIView
from .review_competency_rating import ReviewCompetencyRatingAPIView

from .course import CourseAPIView
from .training_session import TrainingSessionAPIView
from .employee_training import EmployeeTrainingAPIView
from .certification import CertificationAPIView

from .promotion import PromotionAPIView
from .transfer import TransferAPIView
from .disciplinary_case import DisciplinaryCaseAPIView
from .disciplinary_action import DisciplinaryActionAPIView
from .resignation import ResignationAPIView
from .termination import TerminationAPIView
from .employee_offboarding import EmployeeOffboardingAPIView
from .employee_offboarding_task import EmployeeOffboardingTaskAPIView

from .dashboard import (
    OrganizacaoDashboardAPIView,
    TempoPresencaDashboardAPIView,
    SalarioFolhaDashboardAPIView,
    AusenciasDashboardAPIView,
    RecrutamentoDashboardAPIView,
    OnboardingDashboardAPIView,
    DesempenhoDashboardAPIView,
    FormacaoDashboardAPIView,
    CicloVidaDashboardAPIView,
)
