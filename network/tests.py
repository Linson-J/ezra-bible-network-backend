import json
from datetime import date, datetime, time

from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import AppConfig, DailyVerse, Device, MinistryContent, PrayerRequest, Program, SpecialVerse
from .services import is_on_air, now_and_next


def program(**kw):
    defaults = dict(title="Worship", day_of_week=1, start_time=time(7), end_time=time(9))
    defaults.update(kw)
    return Program.objects.create(**defaults)


class ConfigAndContentTests(TestCase):
    def test_config_shape_matches_app_contract(self):
        AppConfig(stream_url="https://x/index.m3u8", announcement="Hi").save()
        data = self.client.get("/api/config").json()
        self.assertEqual(set(data), {"streamUrl", "streamBackupUrl", "isLive", "offlineMessage",
                                     "announcement", "minAppVersion", "forceUpdate", "donationUrl"})
        self.assertEqual(data["streamUrl"], "https://x/index.m3u8")
        self.assertIs(data["isLive"], True)
        self.assertIs(data["forceUpdate"], False)

    def test_config_works_before_anything_is_saved(self):
        self.assertEqual(self.client.get("/api/config").status_code, 200)

    def test_content_shape(self):
        MinistryContent(email="a@b.co", whatsapp="+91").save()
        data = self.client.get("/api/content").json()
        self.assertEqual(set(data), {"about", "address", "email", "phone", "whatsapp", "youtubeUrl",
                                     "facebookUrl", "instagramUrl", "websiteUrl"})
        self.assertEqual(data["email"], "a@b.co")

    def test_singleton_stays_single(self):
        AppConfig(announcement="a").save()
        AppConfig(announcement="b").save()
        self.assertEqual(AppConfig.objects.count(), 1)
        self.assertEqual(AppConfig.load().announcement, "b")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post("/api/config").status_code, 405)


class ScheduleTests(TestCase):
    def test_schedule_shape_and_order(self):
        program(title="Late", day_of_week=2, start_time=time(22), end_time=time(5, 30))
        program(title="Early", day_of_week=1, start_time=time(5, 30), end_time=time(6))
        program(title="Hidden", is_active=False)
        data = self.client.get("/api/schedule").json()
        self.assertEqual([p["title"] for p in data], ["Early", "Late"])
        self.assertEqual(data[1], {
            "id": data[1]["id"], "title": "Late", "speaker": "", "description": "", "dayOfWeek": 2,
            "startTime": "22:00", "endTime": "05:30", "thumbnailUrl": "",
        })
        self.assertIsInstance(data[0]["id"], str)

    def test_overnight_on_air(self):
        p = program(day_of_week=7, start_time=time(22), end_time=time(5, 30))
        # Monday 2026-10-19 03:00 is inside Sunday 22:00 -> Monday 05:30 (wraps the week).
        self.assertTrue(is_on_air(p, datetime(2026, 10, 19, 3, 0)))
        self.assertFalse(is_on_air(p, datetime(2026, 10, 19, 5, 30)))
        self.assertEqual(p.duration_minutes, 450)

    def test_now_and_next(self):
        a = program(title="A", start_time=time(7), end_time=time(9))
        b = program(title="B", start_time=time(9), end_time=time(10))
        on, nxt = now_and_next(datetime(2026, 10, 19, 8, 0))  # a Monday
        self.assertEqual((on, nxt), (a, b))


class VerseTests(TestCase):
    def setUp(self):
        DailyVerse.objects.bulk_create(
            DailyVerse(day=d, reference=f"Ref {d}", text=f"Text {d}") for d in range(1, 367)
        )

    def get(self, **params):
        return self.client.get("/api/verses", params)

    def test_returns_exactly_days_consecutive_dates(self):
        data = self.get(**{"from": "2026-12-30", "days": 4}).json()
        self.assertEqual([v["date"] for v in data], ["2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"])
        self.assertEqual(set(data[0]), {"date", "reference", "text"})
        # Same day-of-year pick as the app's local repository.
        self.assertEqual(data[1]["reference"], "Ref 365")
        self.assertEqual(data[2]["reference"], "Ref 1")

    def test_leap_year_uses_day_366(self):
        data = self.get(**{"from": "2028-12-31", "days": 1}).json()
        self.assertEqual(data[0]["reference"], "Ref 366")

    def test_special_verse_overrides_rotation(self):
        SpecialVerse.objects.create(date=date(2027, 3, 28), reference="Matthew 28:6", text="He is risen")
        data = self.get(**{"from": "2027-03-27", "days": 3}).json()
        self.assertEqual([v["reference"] for v in data], ["Ref 86", "Matthew 28:6", "Ref 88"])

    def test_wraps_when_rotation_is_short(self):
        DailyVerse.objects.filter(day__gt=10).delete()
        data = self.get(**{"from": "2026-01-12", "days": 1}).json()  # day 12 -> 2nd entry
        self.assertEqual(data[0]["reference"], "Ref 2")

    def test_defaults_to_today_and_30_days(self):
        self.assertEqual(len(self.get().json()), 30)

    def test_bad_params(self):
        self.assertEqual(self.get(**{"from": "2026-13-01"}).status_code, 400)
        self.assertEqual(self.get(days="abc").status_code, 400)
        self.assertEqual(self.get(days=0).status_code, 400)
        self.assertEqual(self.get(days=367).status_code, 400)


@override_settings(PRAYER_REQUEST_RATE=3)
class PrayerAndDeviceTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, path, body):
        return self.client.post(path, json.dumps(body) if not isinstance(body, str) else body,
                                content_type="application/json")

    def test_prayer_request_created(self):
        r = self.post("/api/prayer-requests", {"name": " Mary ", "phone": "+91 99", "request": "Healing"})
        self.assertEqual(r.status_code, 201)
        pr = PrayerRequest.objects.get()
        self.assertEqual((pr.name, pr.request, pr.status), ("Mary", "Healing", "new"))

    @override_settings(PRAYER_REQUEST_RATE=100)
    def test_prayer_request_validation(self):
        self.assertEqual(self.post("/api/prayer-requests", {"name": "x", "request": "  "}).status_code, 400)
        self.assertEqual(self.post("/api/prayer-requests", "not json").status_code, 400)
        self.assertEqual(self.post("/api/prayer-requests", ["list"]).status_code, 400)
        self.assertEqual(self.post("/api/prayer-requests", {"request": 5}).status_code, 400)
        self.assertEqual(self.post("/api/prayer-requests", {"request": "x" * 4001}).status_code, 400)
        self.assertFalse(PrayerRequest.objects.exists())

    def test_prayer_request_rate_limited(self):
        codes = [self.post("/api/prayer-requests", {"request": "Pray"}).status_code for _ in range(4)]
        self.assertEqual(codes, [201, 201, 201, 429])

    def test_device_upsert(self):
        self.assertEqual(self.post("/api/devices", {"fcmToken": "abc", "platform": "android"}).status_code, 201)
        self.assertEqual(self.post("/api/devices", {"fcmToken": "abc", "platform": "ios"}).status_code, 201)
        self.assertEqual(Device.objects.get().platform, "ios")
        self.assertEqual(self.post("/api/devices", {"platform": "android"}).status_code, 400)

    def test_csrf_not_required_for_app(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post("/api/prayer-requests", json.dumps({"request": "Pray"}), content_type="application/json")
        self.assertEqual(r.status_code, 201)


class SeedCommandTests(TestCase):
    def test_seed_loads_app_assets(self):
        from django.core.management import call_command
        call_command("seed_ezra", stdout=open("/dev/null", "w"))
        self.assertEqual(DailyVerse.objects.count(), 366)
        self.assertTrue(Program.objects.exists())
        self.assertTrue(AppConfig.objects.exists())
        call_command("seed_ezra", stdout=open("/dev/null", "w"))  # idempotent
        self.assertEqual(DailyVerse.objects.count(), 366)
