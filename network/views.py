"""The JSON API consumed by the Flutter app (lib/repositories/api/).

The contract is defined in the app's README: camelCase keys, dates as
YYYY-MM-DD, times as HH:mm.
"""

import json
import logging
from datetime import date
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import AppConfig, Device, MinistryContent, PrayerRequest, Program
from .services import verses_for

log = logging.getLogger(__name__)

MAX_VERSE_DAYS = 366


def error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def client_ip(request):
    if settings.BEHIND_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def rate_limited(scope, rate_setting, window_setting):
    """Reject a client IP after `rate` calls within `window` seconds."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            rate, window = getattr(settings, rate_setting), getattr(settings, window_setting)
            key = f"rl:{scope}:{client_ip(request)}"
            cache.add(key, 0, window)
            try:
                count = cache.incr(key)
            except ValueError:  # expired between add and incr
                cache.set(key, 1, window)
                count = 1
            if count > rate:
                return error("Too many requests. Please try again later.", status=429)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def clean_str(data, key, max_len):
    value = data.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string.")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"'{key}' must be at most {max_len} characters.")
    return value


@require_GET
def config(request):
    return JsonResponse(AppConfig.load().to_api())


@require_GET
def schedule(request):
    programs = Program.objects.filter(is_active=True)
    return JsonResponse([p.to_api(request) for p in programs], safe=False)


@require_GET
def content(request):
    return JsonResponse(MinistryContent.load().to_api())


@require_GET
def verses(request):
    raw_from = request.GET.get("from")
    try:
        start = date.fromisoformat(raw_from) if raw_from else timezone.localdate()
    except ValueError:
        return error("'from' must be a date in YYYY-MM-DD format.")
    try:
        days = int(request.GET.get("days", "30"))
    except ValueError:
        return error("'days' must be a whole number.")
    if not 1 <= days <= MAX_VERSE_DAYS:
        return error(f"'days' must be between 1 and {MAX_VERSE_DAYS}.")

    data = [
        {"date": v["date"].isoformat(), "reference": v["reference"], "text": v["text"]}
        for v in verses_for(start, days)
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_POST
@rate_limited("prayer", "PRAYER_REQUEST_RATE", "PRAYER_REQUEST_WINDOW_SECONDS")
def prayer_requests(request):
    data = json_body(request)
    if data is None:
        return error("Send a JSON object.")
    try:
        name = clean_str(data, "name", 100)
        phone = clean_str(data, "phone", 30)
        text = clean_str(data, "request", 4000)
    except ValueError as e:
        return error(str(e))
    if not text:
        return error("'request' is required.")

    pr = PrayerRequest.objects.create(name=name, phone=phone, request=text)
    log.info("Prayer request %s received", pr.pk)
    return JsonResponse({"id": pr.pk}, status=201)


@csrf_exempt
@require_POST
@rate_limited("device", "PRAYER_REQUEST_RATE", "PRAYER_REQUEST_WINDOW_SECONDS")
def devices(request):
    data = json_body(request)
    if data is None:
        return error("Send a JSON object.")
    try:
        token = clean_str(data, "fcmToken", 500)
        platform = clean_str(data, "platform", 20) or "android"
    except ValueError as e:
        return error(str(e))
    if not token:
        return error("'fcmToken' is required.")

    device, _ = Device.objects.update_or_create(fcm_token=token, defaults={"platform": platform})
    return JsonResponse({"id": device.pk}, status=201)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})
