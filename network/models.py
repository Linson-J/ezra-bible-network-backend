from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models


class SingletonModel(models.Model):
    """A table that only ever holds row pk=1. Use `Model.load()`."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AppConfig(SingletonModel):
    """GET /api/config. Lets the team control the live stream without an app update."""

    stream_url = models.URLField(
        "Stream URL", max_length=500, blank=True,
        help_text="HLS (.m3u8) URL. Leave empty to use the URL built into the app.",
    )
    stream_backup_url = models.URLField(
        "Backup stream URL", max_length=500, blank=True,
        help_text="Tried right away if the main stream fails.",
    )
    is_live = models.BooleanField(
        "On air", default=True,
        help_text="Off shows the off-air screen with the message below.",
    )
    offline_message = models.CharField(
        max_length=300, blank=True,
        default="We're having trouble reaching the live stream. We'll keep trying.",
    )
    announcement = models.CharField(
        max_length=300, blank=True, help_text="Shown as a banner on the Live tab. Empty hides it.",
    )
    min_app_version = models.CharField(
        "Minimum app version", max_length=20, blank=True, default="1.0.0",
        help_text="e.g. 1.2.0. Older installs see an update prompt.",
    )
    force_update = models.BooleanField(
        default=False, help_text="Block older versions until they update from the Play Store.",
    )
    donation_url = models.URLField("Donation link", max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "app config"
        verbose_name_plural = "app config"

    def __str__(self):
        return "App config"

    def clean(self):
        v = self.min_app_version.strip()
        if v and not all(p.isdigit() for p in v.split(".")):
            raise ValidationError({"min_app_version": "Use numbers separated by dots, e.g. 1.2.0."})

    def to_api(self):
        return {
            "streamUrl": self.stream_url,
            "streamBackupUrl": self.stream_backup_url,
            "isLive": self.is_live,
            "offlineMessage": self.offline_message,
            "announcement": self.announcement,
            "minAppVersion": self.min_app_version,
            "forceUpdate": self.force_update,
            "donationUrl": self.donation_url,
        }


class MinistryContent(SingletonModel):
    """GET /api/content. About text, contact details and social links."""

    about = models.TextField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True,
                                help_text="International format, e.g. +919876543210.")
    youtube_url = models.URLField("YouTube", blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    website_url = models.URLField("Website", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ministry content"
        verbose_name_plural = "ministry content"

    def __str__(self):
        return "Ministry content"

    def to_api(self):
        return {
            "about": self.about,
            "address": self.address,
            "email": self.email,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "youtubeUrl": self.youtube_url,
            "facebookUrl": self.facebook_url,
            "instagramUrl": self.instagram_url,
            "websiteUrl": self.website_url,
        }


class Program(models.Model):
    """One weekly slot. Times are local to the viewer; end <= start runs past midnight."""

    class Day(models.IntegerChoices):
        MONDAY = 1
        TUESDAY = 2
        WEDNESDAY = 3
        THURSDAY = 4
        FRIDAY = 5
        SATURDAY = 6
        SUNDAY = 7

    title = models.CharField(max_length=120)
    speaker = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    day_of_week = models.PositiveSmallIntegerField("Day", choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField(help_text="Earlier than the start time means it ends the next day.")
    thumbnail = models.FileField(
        upload_to="programs/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
        help_text="JPG, PNG or WebP. Overrides the image URL.",
    )
    thumbnail_url = models.URLField("Image URL", max_length=500, blank=True)
    is_active = models.BooleanField("Visible in app", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.start_time:%H:%M} · {self.title}"

    def clean(self):
        if self.start_time and self.end_time and self.start_time == self.end_time:
            raise ValidationError({"end_time": "End time must differ from the start time."})

    @property
    def start_minute(self):
        return self.start_time.hour * 60 + self.start_time.minute

    @property
    def duration_minutes(self):
        d = self.end_time.hour * 60 + self.end_time.minute - self.start_minute
        return d if d > 0 else d + 24 * 60

    @property
    def start_minute_of_week(self):
        return (self.day_of_week - 1) * 24 * 60 + self.start_minute

    @property
    def runs_overnight(self):
        return self.end_time <= self.start_time

    def image_url(self, request=None):
        if self.thumbnail:
            url = self.thumbnail.url
            return request.build_absolute_uri(url) if request else url
        return self.thumbnail_url

    def to_api(self, request=None):
        return {
            "id": str(self.pk),
            "title": self.title,
            "speaker": self.speaker,
            "description": self.description,
            "dayOfWeek": self.day_of_week,
            "startTime": f"{self.start_time:%H:%M}",
            "endTime": f"{self.end_time:%H:%M}",
            "thumbnailUrl": self.image_url(request),
        }


def day_of_year(d: date) -> int:
    return d.timetuple().tm_yday


class DailyVerse(models.Model):
    """The yearly rotation: one verse per day of the year (1-366)."""

    day = models.PositiveSmallIntegerField(
        unique=True, validators=[MinValueValidator(1), MaxValueValidator(366)],
        help_text="Day of the year, 1 = 1 January.",
    )
    reference = models.CharField(max_length=80)
    text = models.TextField()

    class Meta:
        ordering = ["day"]

    def __str__(self):
        return f"Day {self.day} · {self.reference}"


class SpecialVerse(models.Model):
    """A verse pinned to one calendar date (Easter, Christmas...). Beats the rotation."""

    date = models.DateField(unique=True)
    reference = models.CharField(max_length=80)
    text = models.TextField()
    note = models.CharField(max_length=120, blank=True, help_text="Only for your team, e.g. “Easter Sunday”.")

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%d %b %Y} · {self.reference}"


class PrayerRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        PRAYED = "prayed", "Prayed"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    request = models.TextField(max_length=4000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    note = models.TextField("Team note", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or 'Anonymous'} · {self.created_at:%d %b %Y}"


class Device(models.Model):
    """POST /api/devices. Kept for future push notifications."""

    fcm_token = models.CharField(max_length=500, unique=True)
    platform = models.CharField(max_length=20, default="android")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.platform} · {self.fcm_token[:16]}…"
