from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from network.models import AppConfig, DailyVerse, Device, MinistryContent, PrayerRequest, Program, SpecialVerse
from network.services import minutes_until_start, now_and_next, verses_for

from .forms import (AppConfigForm, CopyDayForm, DailyVerseForm, MinistryContentForm, PrayerUpdateForm,
                    ProgramForm, SpecialVerseForm, StaffLoginForm)

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="dashboard:login")


class LoginView(auth_views.LoginView):
    template_name = "dashboard/login.html"
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True


def _greeting(hour):
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"


def _safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else fallback


@staff_required
def home(request):
    now = timezone.localtime()
    on_air, upcoming = now_and_next(now)
    today = verses_for(now.date(), 1)
    counts = PrayerRequest.objects.aggregate(
        new=Count("pk", filter=Q(status=PrayerRequest.Status.NEW)),
        week=Count("pk", filter=Q(created_at__gte=now - timedelta(days=7))),
    )
    return render(request, "dashboard/home.html", {
        "nav": "home",
        "greeting": _greeting(now.hour),
        "now": now,
        "config": AppConfig.load(),
        "on_air": on_air,
        "upcoming": upcoming,
        "upcoming_in": minutes_until_start(upcoming, now) if upcoming else None,
        "verse": today[0] if today else None,
        "stats": {
            "new_prayers": counts["new"],
            "week_prayers": counts["week"],
            "programs": Program.objects.filter(is_active=True).count(),
            "devices": Device.objects.count(),
        },
        "recent_prayers": PrayerRequest.objects.all()[:4],
    })


@staff_required
@require_POST
def toggle_live(request):
    cfg = AppConfig.load()
    cfg.is_live = not cfg.is_live
    cfg.save()
    messages.success(request, "You're on air. The app will connect to the stream." if cfg.is_live
                     else "Off air. The app now shows your off-air message.")
    return redirect(_safe_next(request, reverse("dashboard:home")))


@staff_required
def live(request):
    cfg = AppConfig.load()
    form = AppConfigForm(request.POST or None, instance=cfg)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Live settings saved. The app picks them up on next open.")
        return redirect("dashboard:live")
    return render(request, "dashboard/live.html", {"nav": "live", "form": form, "config": cfg})


# ---- Schedule ---------------------------------------------------------------

def _day_param(request, default):
    try:
        d = int(request.GET.get("day", default))
    except ValueError:
        return default
    return d if 1 <= d <= 7 else default


@staff_required
def schedule(request):
    now = timezone.localtime()
    day = _day_param(request, now.isoweekday())
    programs = list(Program.objects.filter(day_of_week=day))
    on_air, _ = now_and_next(now, [p for p in programs if p.is_active])
    per_day = dict(Program.objects.values_list("day_of_week").annotate(n=Count("pk")))
    days = [{"num": n, "label": label, "short": label[:3], "count": per_day.get(n, 0), "today": n == now.isoweekday()}
            for n, label in Program.Day.choices]
    return render(request, "dashboard/schedule.html", {
        "nav": "schedule", "day": day, "day_label": Program.Day(day).label, "days": days,
        "programs": programs, "on_air": on_air,
    })


@staff_required
def program_form(request, pk=None):
    program = get_object_or_404(Program, pk=pk) if pk else None
    initial = {} if program else {"day_of_week": _day_param(request, timezone.localtime().isoweekday())}
    form = ProgramForm(request.POST or None, request.FILES or None, instance=program, initial=initial)
    if request.method == "POST" and form.is_valid():
        p = form.save()
        messages.success(request, f"“{p.title}” {'updated' if program else 'added'}.")
        return redirect(f"{reverse('dashboard:schedule')}?day={p.day_of_week}")
    return render(request, "dashboard/program_form.html", {"nav": "schedule", "form": form, "program": program})


@staff_required
@require_POST
def program_delete(request, pk):
    p = get_object_or_404(Program, pk=pk)
    day, title = p.day_of_week, p.title
    p.delete()
    messages.success(request, f"“{title}” removed from the schedule.")
    return redirect(f"{reverse('dashboard:schedule')}?day={day}")


@staff_required
@require_POST
def program_toggle(request, pk):
    p = get_object_or_404(Program, pk=pk)
    p.is_active = not p.is_active
    p.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"“{p.title}” is now {'visible' if p.is_active else 'hidden'} in the app.")
    return redirect(f"{reverse('dashboard:schedule')}?day={p.day_of_week}")


@staff_required
@require_POST
def schedule_copy(request):
    form = CopyDayForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Pick at least one day to copy to.")
        return redirect(f"{reverse('dashboard:schedule')}?day={request.POST.get('source', 1)}")
    src = form.cleaned_data["source"]
    targets = [t for t in form.cleaned_data["targets"] if t != src]
    source = list(Program.objects.filter(day_of_week=src))
    with transaction.atomic():
        if form.cleaned_data["replace"]:
            Program.objects.filter(day_of_week__in=targets).delete()
        Program.objects.bulk_create([
            Program(title=p.title, speaker=p.speaker, description=p.description, day_of_week=t,
                    start_time=p.start_time, end_time=p.end_time, thumbnail=p.thumbnail,
                    thumbnail_url=p.thumbnail_url, is_active=p.is_active)
            for t in targets for p in source
        ])
    names = ", ".join(Program.Day(t).label for t in targets)
    messages.success(request, f"Copied {len(source)} programs to {names}.")
    return redirect(f"{reverse('dashboard:schedule')}?day={src}")


# ---- Verses -----------------------------------------------------------------

@staff_required
def verses(request):
    today = timezone.localdate()
    q = request.GET.get("q", "").strip()
    rotation = DailyVerse.objects.all()
    if q:
        rotation = rotation.filter(Q(reference__icontains=q) | Q(text__icontains=q))
    page = Paginator(rotation, 30).get_page(request.GET.get("page"))
    return render(request, "dashboard/verses.html", {
        "nav": "verses", "q": q, "page": page, "today": today,
        "upcoming": verses_for(today, 14),
        "specials": SpecialVerse.objects.filter(date__gte=today),
        "rotation_count": DailyVerse.objects.count(),
    })


@staff_required
def daily_verse_edit(request, day):
    verse = get_object_or_404(DailyVerse, day=day)
    form = DailyVerseForm(request.POST or None, instance=verse)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Day {day} updated.")
        return redirect(_safe_next(request, reverse("dashboard:verses")))
    return render(request, "dashboard/verse_form.html", {
        "nav": "verses", "form": form, "title": f"Day {day} of the year",
        "subtitle": "Part of the yearly rotation. Used every year on this day unless a special verse is set.",
    })


@staff_required
def special_verse_form(request, pk=None):
    special = get_object_or_404(SpecialVerse, pk=pk) if pk else None
    initial = {}
    if not special and request.GET.get("date"):
        try:
            initial["date"] = date.fromisoformat(request.GET["date"])
        except ValueError:
            pass
    form = SpecialVerseForm(request.POST or None, instance=special, initial=initial)
    if request.method == "POST" and form.is_valid():
        s = form.save()
        messages.success(request, f"Special verse set for {s.date:%A, %d %B}.")
        return redirect("dashboard:verses")
    return render(request, "dashboard/verse_form.html", {
        "nav": "verses", "form": form, "special": special,
        "title": "Edit special verse" if special else "Special verse",
        "subtitle": "Pinned to one date. It replaces the rotation verse for that day only.",
    })


@staff_required
@require_POST
def special_verse_delete(request, pk):
    s = get_object_or_404(SpecialVerse, pk=pk)
    s.delete()
    messages.success(request, f"Special verse for {s.date:%d %B} removed. The rotation verse is back.")
    return redirect("dashboard:verses")


# ---- Prayer requests ----------------------------------------------------------

@staff_required
def prayers(request):
    status = request.GET.get("status", PrayerRequest.Status.NEW)
    q = request.GET.get("q", "").strip()
    qs = PrayerRequest.objects.all()
    if status in PrayerRequest.Status.values:
        qs = qs.filter(status=status)
    else:
        status = "all"
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(request__icontains=q))
    counts = dict(PrayerRequest.objects.values_list("status").annotate(n=Count("pk")))
    tabs = [{"key": k, "label": label, "count": counts.get(k, 0)} for k, label in PrayerRequest.Status.choices]
    tabs.append({"key": "all", "label": "All", "count": sum(counts.values())})
    return render(request, "dashboard/prayers.html", {
        "nav": "prayers", "status": status, "q": q, "tabs": tabs,
        "page": Paginator(qs, 20).get_page(request.GET.get("page")),
    })


@staff_required
@require_POST
def prayer_update(request, pk):
    pr = get_object_or_404(PrayerRequest, pk=pk)
    data = request.POST.copy()
    data.setdefault("status", pr.status)
    data.setdefault("note", pr.note)
    form = PrayerUpdateForm(data, instance=pr)
    if form.is_valid():
        form.save()
        label = {"prayed": "Marked as prayed for.", "archived": "Archived.", "new": "Moved back to New."}
        messages.success(request, label.get(pr.status) if "status" in request.POST else "Note saved.")
    else:
        messages.error(request, "Couldn't update that request.")
    return redirect(_safe_next(request, reverse("dashboard:prayers")))


@staff_required
@require_POST
def prayer_delete(request, pk):
    get_object_or_404(PrayerRequest, pk=pk).delete()
    messages.success(request, "Prayer request deleted.")
    return redirect(_safe_next(request, reverse("dashboard:prayers")))


# ---- Content ------------------------------------------------------------------

@staff_required
def content(request):
    form = MinistryContentForm(request.POST or None, instance=MinistryContent.load())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ministry details saved.")
        return redirect("dashboard:content")
    return render(request, "dashboard/content.html", {"nav": "content", "form": form})
