"""pytest setup for this application's pytest-style tests (the hr module).

The tenant fixtures (bootstrap_tenant, activate_module) are the framework's
public test helpers - the same ones django_resaas's own tests use. The other
apps' tests are Django TestCase and run with `manage.py test`.
"""
pytest_plugins = ["django_resaas.testing.pytest_plugin"]
