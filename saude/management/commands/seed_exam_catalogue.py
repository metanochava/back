"""Standard exam catalogue (types, classes, exams and their parameters).

    python manage.py seed_exam_catalogue --entity Amal
    python manage.py seed_exam_catalogue --entity Amal --branch Sede --dry-run

Real configuration, not demo data: safe in production. Additive and
idempotent - only what is missing is created, nothing existing is changed.
Reference ranges are never seeded (laboratory configuration). See
saude/services/exam_catalogue_service.py.
"""
from django.core.management.base import BaseCommand, CommandError

from saude.services import exam_catalogue_service
from saude.services.exam_catalogue_service import CatalogueSeedError


class Command(BaseCommand):
    help = "Creates the standard exam catalogue (types, classes, exams, parameters) of an Entity."

    def add_arguments(self, parser):
        parser.add_argument("--entity", required=True, help="Entity name or id.")
        parser.add_argument("--branch", help="Branch name or id (required when the Entity has several).")
        parser.add_argument("--dry-run", action="store_true", help="Validate and count, write nothing.")

    def handle(self, *args, **options):
        try:
            report = exam_catalogue_service.seed(
                entity=options["entity"], branch=options["branch"], dry_run=options["dry_run"],
            )
        except CatalogueSeedError as error:
            raise CommandError(str(error))

        heading = "DRY RUN - nothing written" if options["dry_run"] else "Exam catalogue"
        self.stdout.write(self.style.MIGRATE_HEADING(heading))
        self.stdout.write(f"Entity: {report.entity} | Branch: {report.branch}")
        for kind in ("types", "classes", "exams", "parameters"):
            self.stdout.write(f"  {kind:10} created {report.created[kind]:4}   already there {report.existing[kind]:4}")
        self.stdout.write(self.style.SUCCESS("Reference ranges: none seeded - configure them per laboratory."))
