# Medication names are stored in capitals (Medicamento.save()): the rows
# saved before that are converted once. Reverse is a no-op (the original
# case is not kept).
from django.db import migrations
from django.db.models.functions import Upper


def to_upper(apps, schema_editor):
    Medicamento = apps.get_model("saude", "Medicamento")
    manager = getattr(Medicamento, "all_objects", Medicamento._base_manager)
    manager.update(descricao=Upper("descricao"))
    manager.exclude(principio_ativo__isnull=True).update(principio_ativo=Upper("principio_ativo"))


class Migration(migrations.Migration):

    dependencies = [
        ("saude", "0015_favouriteexam"),
    ]

    operations = [
        migrations.RunPython(to_upper, migrations.RunPython.noop),
    ]
