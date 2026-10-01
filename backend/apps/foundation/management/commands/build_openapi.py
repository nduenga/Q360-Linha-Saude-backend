from django.core.management.base import BaseCommand, CommandError

from config.openapi import build


class Command(BaseCommand):
    help = "Generate backend/schema.yml and update the ART-006 contract from the code."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Fail if the files are out of date.")

    def handle(self, *args, **options):
        generated, contract = build.build(write=not options["check"])
        if options["check"]:
            if build.GENERATED.read_text(encoding="utf-8") != generated or build.CONTRACT.read_text(encoding="utf-8") != contract:
                raise CommandError("OpenAPI files are out of date: run `manage.py build_openapi`.")
            self.stdout.write("OpenAPI files are up to date.")
        else:
            self.stdout.write(f"Wrote {build.GENERATED} and {build.CONTRACT}")
