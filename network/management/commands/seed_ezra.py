"""Load the app's sample data (copied from the Flutter app's assets/data/).

    python manage.py seed_ezra            # only fills empty tables
    python manage.py seed_ezra --replace  # wipes schedule + verses first
    python manage.py seed_ezra --from ../ezra-bible-network/assets/data
"""

import json
from datetime import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from network.models import AppConfig, DailyVerse, MinistryContent, Program

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def hhmm(value):
    h, m = value.split(":")
    return time(int(h), int(m))


class Command(BaseCommand):
    help = "Seed config, contact content, the weekly schedule and 366 daily verses."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="source", default=str(SEED_DIR),
                            help="Folder with app_config.json, app_content.json, schedule.json, verses.json.")
        parser.add_argument("--replace", action="store_true",
                            help="Delete existing programs and daily verses before loading.")

    def read(self, folder, name):
        path = folder / name
        if not path.exists():
            raise CommandError(f"Missing {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @transaction.atomic
    def handle(self, *args, source, replace, **options):
        folder = Path(source)

        if replace:
            Program.objects.all().delete()
            DailyVerse.objects.all().delete()

        if not AppConfig.objects.exists() or replace:
            c = self.read(folder, "app_config.json")
            AppConfig(
                stream_url=c.get("streamUrl", ""),
                stream_backup_url=c.get("streamBackupUrl", ""),
                is_live=c.get("isLive", True),
                offline_message=c.get("offlineMessage", ""),
                announcement=c.get("announcement", ""),
                min_app_version=c.get("minAppVersion", ""),
                force_update=c.get("forceUpdate", False),
                donation_url=c.get("donationUrl", ""),
            ).save()
            self.stdout.write("  app config")

        if not MinistryContent.objects.exists() or replace:
            c = self.read(folder, "app_content.json")
            MinistryContent(
                about=c.get("about", ""), address=c.get("address", ""), email=c.get("email", ""),
                phone=c.get("phone", ""), whatsapp=c.get("whatsapp", ""),
                youtube_url=c.get("youtubeUrl", ""), facebook_url=c.get("facebookUrl", ""),
                instagram_url=c.get("instagramUrl", ""), website_url=c.get("websiteUrl", ""),
            ).save()
            self.stdout.write("  ministry content")

        if not Program.objects.exists():
            programs = [
                Program(
                    title=p["title"], speaker=p.get("speaker", ""), description=p.get("description", ""),
                    day_of_week=p["dayOfWeek"], start_time=hhmm(p["startTime"]), end_time=hhmm(p["endTime"]),
                    thumbnail_url=p.get("thumbnailUrl", ""),
                )
                for p in self.read(folder, "schedule.json")
            ]
            Program.objects.bulk_create(programs)
            self.stdout.write(f"  {len(programs)} programs")

        if not DailyVerse.objects.exists():
            verses = [
                DailyVerse(day=v["day"], reference=v["reference"], text=v["text"])
                for v in self.read(folder, "verses.json")
            ]
            DailyVerse.objects.bulk_create(verses)
            self.stdout.write(f"  {len(verses)} daily verses")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
