"""pytest setup for this application's tests.

Discovery covers every module (pyproject.toml testpaths); the modules' Django
TestCase classes run under pytest too, so one `pytest` runs them all.

The tenant fixtures (bootstrap_tenant, activate_module) are the framework's
public test helpers - the same ones django_resaas's own tests use.
"""
import pytest

pytest_plugins = ["django_resaas.testing.pytest_plugin"]


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    # bootstrap_tenant syncs the permissions of every model of MY_APPS (the
    # Root group gets them all). Inside a test that is ~2500 rows written and
    # rolled back every time; created once here, each test only finds them.
    # The EntityType the sync needs is removed again, so tests start from the
    # same data as before.
    from django.apps import apps
    from django_resaas.saas.core.signals.permissions import create_model_permissions
    from django_resaas.saas.models.entity_type import EntityType

    with django_db_blocker.unblock():
        entity_type = EntityType.objects.create(name="Test session permissions", state="Active")
        create_model_permissions(sender=None, app_config=apps.get_app_config("django_resaas"))
        entity_type.delete()


def pytest_configure(config):
    # every test tenant creates users: the production hasher (PBKDF2, ~1M
    # iterations) made hashing a large share of the suite's time. Tests only
    # check that passwords work, not how strongly they are stored.
    from django.conf import settings

    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
