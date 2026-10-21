import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from integrations.models import SourceSystem, StagedRecord
from integrations.pipeline import run_sync
from integrations.sources import all_sources


class Command(BaseCommand):
    help = "Sync one or more source systems (e.g. smis) into the core tables."

    def add_arguments(self, parser):
        parser.add_argument("sources", nargs="+", help="source codes, or 'all'")
        parser.add_argument("--scale", type=float, default=1.0,
                            help="mock only: shrink the volumes, e.g. 0.1")
        parser.add_argument("--seed", type=int, default=2026,
                            help="mock only: a different seed gives different records")

    def handle(self, *args, **options):
        available = all_sources()
        codes = list(available) if options["sources"] == ["all"] else options["sources"]
        unknown = [code for code in codes if code not in available]
        if unknown:
            raise CommandError(
                f"unknown source: {', '.join(unknown)}. Available: {', '.join(available)}"
            )

        for code in codes:
            source = available[code]
            system = SourceSystem.objects.filter(code=code).first()
            if system and system.mode == SourceSystem.Mode.LIVE:
                raise CommandError(f"{code} is set to live, but there is no live connector yet")

            connector = source.mock_connector(seed=options["seed"], scale=options["scale"])
            run = run_sync(connector, source.loader, source.name)
            self.stdout.write(
                f"{code}: received {run.received}, created {run.created}, "
                f"updated {run.updated}, rejected {run.rejected} (run {run.pk})"
            )
            if run.rejected:
                # group reasons by their wording, hiding the value: "student '...' is not known"
                rejected = StagedRecord.objects.filter(
                    run=run, status=StagedRecord.Status.REJECTED
                ).values_list("errors", flat=True)
                reasons = Counter(
                    re.sub(r"'[^']*'", "'...'", reason) for errors in rejected for reason in errors
                )
                for reason, count in reasons.most_common(5):
                    self.stdout.write(f"  rejected {count}: {reason}")
