from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from network.models import AppConfig, DailyVerse, PrayerRequest, Program, SpecialVerse


class DashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user("team", password="pw-strong-123", is_staff=True)
        self.client.force_login(self.staff)
        self.program = Program.objects.create(title="Worship", day_of_week=1, start_time=time(7), end_time=time(9))
        DailyVerse.objects.create(day=1, reference="Genesis 1:1", text="In the beginning")
        self.prayer = PrayerRequest.objects.create(name="Mary", request="Healing")

    def test_all_pages_render(self):
        for name, args in [("home", []), ("live", []), ("schedule", []), ("program-new", []),
                           ("program-edit", [self.program.pk]), ("verses", []), ("daily-verse-edit", [1]),
                           ("special-new", []), ("prayers", []), ("content", [])]:
            with self.subTest(name):
                r = self.client.get(reverse(f"dashboard:{name}", args=args))
                self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:prayers") + "?status=all&q=Mary").status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:schedule") + "?day=9").status_code, 200)

    def test_requires_staff(self):
        self.client.logout()
        r = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(r, reverse("dashboard:login") + "?next=/")
        get_user_model().objects.create_user("viewer", password="pw-strong-123")
        r = self.client.post(reverse("dashboard:login"), {"username": "viewer", "password": "pw-strong-123"})
        self.assertContains(r, "doesn&#x27;t have dashboard access")

    def test_login(self):
        self.client.logout()
        r = self.client.post(reverse("dashboard:login"), {"username": "team", "password": "pw-strong-123"})
        self.assertRedirects(r, reverse("dashboard:home"))

    def test_toggle_live(self):
        self.client.post(reverse("dashboard:toggle-live"), {"next": "/schedule/"})
        self.assertFalse(AppConfig.load().is_live)
        r = self.client.post(reverse("dashboard:toggle-live"), {"next": "https://evil.example"})
        self.assertRedirects(r, reverse("dashboard:home"))
        self.assertTrue(AppConfig.load().is_live)

    def test_save_config_shows_in_api(self):
        r = self.client.post(reverse("dashboard:live"), {
            "is_live": "on", "offline_message": "Back soon", "announcement": "Easter at 7",
            "stream_url": "https://cdn.example/live/index.m3u8", "stream_backup_url": "",
            "min_app_version": "1.2.0", "donation_url": "",
        })
        self.assertRedirects(r, reverse("dashboard:live"))
        self.assertEqual(self.client.get("/api/config").json()["announcement"], "Easter at 7")

    def test_bad_version_rejected(self):
        r = self.client.post(reverse("dashboard:live"), {"min_app_version": "v1.beta"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "numbers separated by dots")

    def test_program_crud(self):
        r = self.client.post(reverse("dashboard:program-new"), {
            "title": "Night", "day_of_week": 3, "start_time": "22:00", "end_time": "05:30", "is_active": "on",
        })
        self.assertRedirects(r, reverse("dashboard:schedule") + "?day=3")
        p = Program.objects.get(title="Night")
        self.client.post(reverse("dashboard:program-toggle", args=[p.pk]))
        p.refresh_from_db()
        self.assertFalse(p.is_active)
        self.client.post(reverse("dashboard:program-delete", args=[p.pk]))
        self.assertFalse(Program.objects.filter(pk=p.pk).exists())

    def test_program_same_start_end_rejected(self):
        r = self.client.post(reverse("dashboard:program-new"), {
            "title": "Bad", "day_of_week": 1, "start_time": "08:00", "end_time": "08:00",
        })
        self.assertContains(r, "End time must differ")

    def test_copy_day(self):
        r = self.client.post(reverse("dashboard:schedule-copy"), {"source": 1, "targets": [2, 3]})
        self.assertRedirects(r, reverse("dashboard:schedule") + "?day=1")
        self.assertEqual(Program.objects.filter(title="Worship").count(), 3)
        self.client.post(reverse("dashboard:schedule-copy"), {"source": 1, "targets": [2], "replace": "on"})
        self.assertEqual(Program.objects.filter(day_of_week=2).count(), 1)

    def test_special_verse(self):
        self.client.post(reverse("dashboard:special-new"), {"date": "2027-03-28", "reference": "Mt 28:6", "text": "Risen"})
        s = SpecialVerse.objects.get()
        data = self.client.get("/api/verses", {"from": "2027-03-28", "days": 1}).json()
        self.assertEqual(data[0]["reference"], "Mt 28:6")
        self.client.post(reverse("dashboard:special-delete", args=[s.pk]))
        self.assertFalse(SpecialVerse.objects.exists())

    def test_prayer_workflow(self):
        url = reverse("dashboard:prayer-update", args=[self.prayer.pk])
        self.client.post(url, {"status": "prayed"})
        self.client.post(url, {"note": "Called her"})
        self.prayer.refresh_from_db()
        self.assertEqual((self.prayer.status, self.prayer.note), ("prayed", "Called her"))
        self.client.post(reverse("dashboard:prayer-delete", args=[self.prayer.pk]))
        self.assertFalse(PrayerRequest.objects.exists())

    def test_logout(self):
        r = self.client.post(reverse("dashboard:logout"))
        self.assertRedirects(r, reverse("dashboard:login"))
