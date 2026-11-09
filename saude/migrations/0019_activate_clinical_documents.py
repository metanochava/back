"""Clinical documents created with TimeModel's default state ('Inactive') -
an exam request saved from the schema form, a lab result written by the
result service - were left out of the right-menu history, which lists only
Active documents (HistoryList: state=Active). 'Inactive' means nothing for
these documents (cancelling goes through the document edit policy, removing
through the soft delete), so the ones not deleted become Active. Result
folders (tipo Folder) are left as they are. The reverse does nothing."""
from django.db import migrations

MODELS = ("AtestadoMedico", "ReceitaMedica", "PedidoExameMedico", "ResultadoExameMedico")


def activate(apps, schema_editor):
    for name in MODELS:
        Model = apps.get_model("saude", name)
        rows = Model.objects.filter(state="Inactive")
        if any(f.name == "deleted_at" for f in Model._meta.get_fields()):
            rows = rows.filter(deleted_at__isnull=True)
        if name == "ResultadoExameMedico":
            rows = rows.exclude(tipo="Folder")
        rows.update(state="Active")


class Migration(migrations.Migration):

    dependencies = [
        ("saude", "0018_agenda_especialidade"),
    ]

    operations = [
        migrations.RunPython(activate, migrations.RunPython.noop),
    ]
