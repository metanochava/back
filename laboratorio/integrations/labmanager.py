"""Remote access to a PHYSICAL workstation (a remote-desktop tool): the one
door between laboratorio and such a tool.

The virtual labs (the former Lab Manager) live in laboratorio itself
(services/machine_service.py, manage.py lab); this adapter is only for
opening a remote session on a real computer of a room. By default nothing is
opened (NullLabManagerAdapter): the access is authorised and audited here.
A real tool is plugged in with

    LABORATORIO_REMOTE_ADAPTER = "<module>.<Class>"   (settings)
"""
from django.conf import settings
from django.utils.module_loading import import_string


class LabManagerAdapter:
    """What laboratorio asks of the Lab Manager. Every method may raise; the
    caller turns a failure into a 502 and never records a remote access that
    the Lab Manager refused."""

    name = "abstract"
    connected = False

    def start_remote_access(self, *, workstation, teacher, session, expires_at):
        """Open a remote session to the workstation until expires_at.
        Returns {"ref": "<id in the Lab Manager>", "url": "<where the teacher connects>"} or None."""
        raise NotImplementedError

    def end_remote_access(self, *, ref):
        raise NotImplementedError

    def workstation_status(self, *, workstation):
        """{"online": bool, ...} or None when unknown."""
        raise NotImplementedError


class NullLabManagerAdapter(LabManagerAdapter):
    """No Lab Manager: the access is authorised and audited here, nothing is
    opened remotely (no ref, no url)."""

    name = "none"
    connected = False

    def start_remote_access(self, **kwargs):
        return None

    def end_remote_access(self, **kwargs):
        return None

    def workstation_status(self, **kwargs):
        return None


def get_adapter():
    path = getattr(settings, "LABORATORIO_REMOTE_ADAPTER", "")
    return import_string(path)() if path else NullLabManagerAdapter()
