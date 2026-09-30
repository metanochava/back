"""The HR models' explicit RESAAS routes follow the list_<model> convention
(moved here from django_resaas's test_schema_routes_list when HR became this
application's module)."""
import pytest

from django_resaas.saas.core.schema.builder import ResaasSchemaBuilder
from hr.models.employee import Employee
from hr.models.job_position import JobPosition

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("Model", [Employee, JobPosition])
def test_list_route_matches_model_not_add_route(Model):
    routes = ResaasSchemaBuilder(Model=Model).build_routes()

    assert routes["list"] == "list_" + routes["add"].removeprefix("add_")
    assert routes["list"] != routes["add"]
