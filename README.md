# Ezra Bible Network — Backend

Django backend for the [Ezra Bible Network](../../project/ezra-bible-network) Flutter app. It has two parts:

- **JSON API** (`/api/…`). It implements the contract in the app's README exactly, so the app only needs `DATA_SOURCE=api` and `API_BASE_URL` in its `.env`.
- **Team dashboard** (`/`). A responsive staff UI for desktop and phone. Use it to go on or off air, edit the weekly schedule, manage daily verses, read prayer requests and update contact details.

Python 3.12+ and Django 6.0. SQLite by default, PostgreSQL optional.

## Quick start

```bash
python3 -m venv .venv            # or: uv venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env             # DEBUG=true is fine locally
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_ezra          # sample schedule + 366 KJV verses from the app
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000 and sign in. Only **staff** accounts can use the dashboard. Superusers also get the raw Django admin at `/admin/`.

To add a team member, run `createsuperuser`, or in `/admin/` add a user and tick **Staff status**.

## Connect the Flutter app

In the app's `.env`:

```properties
DATA_SOURCE=api
API_BASE_URL=http://10.0.2.2:8000        # Android emulator → your computer
# API_BASE_URL=http://192.168.1.20:8000  # real phone on the same Wi-Fi (add the IP to ALLOWED_HOSTS)
# API_BASE_URL=https://api.ezrabiblenetwork.com
```

Then rebuild the app. For plain `http://` on a real device, Android needs cleartext traffic allowed. Use HTTPS in production.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/config` | Stream URLs, on-air flag, offline message, announcement, min version, force update, donation link |
| GET | `/api/schedule` | Visible programs, ordered by day then start time. `id` is a string |
| GET | `/api/content` | About, contact details, social links |
| GET | `/api/verses?from=YYYY-MM-DD&days=30` | Exactly `days` consecutive dates (1–366). `from` defaults to today |
| POST | `/api/prayer-requests` | `{ name, phone, request }` → `201`. `request` is required. Rate-limited per IP |
| POST | `/api/devices` | `{ fcmToken, platform }` → `201`. Upserts by token |
| GET | `/api/health` | `{ "status": "ok" }` for uptime checks |

Errors are `{ "error": "…" }` with status 400, 405 or 429.

**Verse logic** matches the app's offline fallback. A *special verse* pinned to a date wins. Otherwise the verse is picked by day of year (1–366) from the rotation, so a backend outage and the API give the same verse.

## Dashboard

| Page | What you can do |
|---|---|
| Overview | See on-air status, now playing and up next, today's verse, new prayer requests. One-tap **Go off air / Go live** |
| Live stream | Change the stream and backup URLs, offline message, Live-tab announcement, minimum app version / force update, donation link |
| Schedule | View day by day with a "now" marker, add, edit, hide or delete programs, upload thumbnails, **copy a day** to other days. Overnight slots (end < start) are supported |
| Daily verse | Today's verse, the next 14 days, **special verses** for set dates, and searchable editing of the 366-day rotation |
| Prayer requests | Filter by New / Prayed / Archived, search, mark as prayed, add a team note, call or WhatsApp the person |
| Ministry details | About text, address, email, phone, WhatsApp, social links |

The dashboard uses the app's palette (deep indigo, royal purple, gold) with a serif face for scripture. The default is dark, and a parchment light theme is under **Theme**. On phones the sidebar becomes a bottom tab bar.

## Tests

```bash
DEBUG=true .venv/bin/python manage.py test
```

## Deploy (outline)

```bash
# .env: DEBUG=false, SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, BEHIND_PROXY=true
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_ezra            # first deploy only; skips tables that already have data
gunicorn ezra.wsgi --bind 0.0.0.0:8000 --workers 3
```

WhiteNoise serves static files. Put nginx or your host's HTTPS proxy in front. Keep `MEDIA_ROOT` (uploaded thumbnails) and the database on persistent storage. Run `python manage.py check --deploy` to confirm the settings.

The prayer-request rate limit uses Django's in-process cache. With several gunicorn workers each worker counts separately. Configure a shared cache (Redis or the database cache) if you need a strict limit.

## Layout

```
ezra/                 settings (all via env), urls
network/              models, JSON API, verse/schedule logic, seed_ezra command, seed/*.json
dashboard/            staff UI: views, forms, templates, static (app.css, app.js, logo)
```
