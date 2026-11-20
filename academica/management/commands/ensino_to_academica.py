"""Rename the former "ensino" app to "academica" in the database, without
moving any row (docs/progress/ensino-modular.md).

    python manage.py ensino_to_academica --dry-run
    python manage.py ensino_to_academica
    python manage.py ensino_to_academica --reverse      # back to "ensino"

What it changes (idempotent; run BEFORE `migrate academica --fake-initial`):

- django_content_type: app_label "ensino" -> "academica". The permissions
  keep their ids, so every profile keeps its assignments;
- the App catalogue row "ensino" -> "academica". Its EntityType / Entity
  activations follow (same row). When an "academica" row already exists,
  the activations are linked to it and the old row is made Inactive (never
  deleted).

The tables are untouched: the academica models keep the ensino_* table names
(Meta.db_table).
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from django_resaas.saas.models.app import App
from django_resaas.saas.models.entity_app import EntityApp
from django_resaas.saas.models.entity_type_app import EntityTypeApp


class Command(BaseCommand):
    help = 'Rename the former "ensino" app to "academica" (content types, App catalogue). No row moves.'

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")
        parser.add_argument("--reverse", action="store_true", help='Rename "academica" back to "ensino".')

    def handle(self, *args, **options):
        old, new = ("academica", "ensino") if options["reverse"] else ("ensino", "academica")
        dry = options["dry_run"]
        report = {"content_types": 0, "content_type_clashes": [], "app": "", "activations_moved": 0}

        with transaction.atomic():
            existing = set(ContentType.objects.filter(app_label=new).values_list("model", flat=True))
            for ct in ContentType.objects.filter(app_label=old):
                if ct.model in existing:
                    report["content_type_clashes"].append(ct.model)
                    continue
                report["content_types"] += 1
                if not dry:
                    ct.app_label = new
                    ct.save(update_fields=["app_label"])

            old_app = App.objects.filter(name=old).first()
            new_app = App.objects.filter(name=new).first()
            if old_app and not new_app:
                report["app"] = f"renamed {old} -> {new}"
                if not dry:
                    old_app.name = new
                    old_app.save(update_fields=["name"])
            elif old_app and new_app:
                for model, key in ((EntityTypeApp, "entity_type_id"), (EntityApp, "entity_id")):
                    for link in model.objects.filter(app=old_app):
                        report["activations_moved"] += 1
                        if not dry:
                            model.objects.get_or_create(app=new_app, **{key: getattr(link, key)},
                                                        defaults={"state": link.state})
                report["app"] = f"{new} already exists: activations linked to it, {old} made Inactive"
                if not dry:
                    old_app.state = "Inactive"
                    old_app.save(update_fields=["state"])
            else:
                report["app"] = f"no {old} row (nothing to rename)"

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.MIGRATE_HEADING("DRY RUN - nothing written" if dry else f"{old} -> {new}"))
        self.stdout.write(f"Content types relabelled: {report['content_types']}")
        if report["content_type_clashes"]:
            self.stdout.write(self.style.WARNING(f"Already under {new} (left as they are): {report['content_type_clashes']}"))
        self.stdout.write(f"App catalogue: {report['app']}")
        if report["activations_moved"]:
            self.stdout.write(f"Activations linked to {new}: {report['activations_moved']}")
