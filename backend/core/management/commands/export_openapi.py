import json
from pathlib import Path

from django.core.management.base import BaseCommand

from circuit.api import api


class Command(BaseCommand):
    help = "Write the OpenAPI spec to a file (the api-client is generated from it)."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **opts):
        Path(opts["path"]).write_text(json.dumps(api.get_openapi_schema(), indent=2, sort_keys=True) + "\n")
        self.stdout.write(f"wrote {opts['path']}")
