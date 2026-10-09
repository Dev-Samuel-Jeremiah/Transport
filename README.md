# Freightline — Transport Business Management System

A Django web app for running a transport/logistics business, with two
dedicated dashboards:

- **Admin dashboard** — register companies (this also creates their login),
  register drivers under a company, view every compliance document on file,
  and track all trucks across the network.
- **Company dashboard** — manage your own trucks and drivers, create
  transits (trips), and post tracking updates as a shipment moves.

Truck/transit tracking works with **manual status + location updates today**,
and the data model has GPS-ready fields (`gps_device_id`, `latitude`,
`longitude`, `gps_last_ping_at` on `Truck`) so a real GPS/telematics feed can
be wired in later without changing the schema — it would just write to the
same fields a manual update writes to today.

## Project layout

```
transport_erp/
├── accounts/     custom User model (ADMIN / COMPANY roles), login/logout, role-based mixins
├── companies/    Company + CompanyDocument models, admin-side company registration & docs
├── drivers/      Driver + DriverDocument models, admin registration, company read view
├── trucks/       Truck + TruckDocument models, admin tracking board, company fleet CRUD
├── transit/      Transit + TrackingUpdate models, company trip lifecycle, admin oversight
├── dashboard/    role-based redirect + the two dashboard home pages
├── templates/    base layout + login page
├── static/css/   design system (styles.css)
└── transport_erp/  Django project settings/urls
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then open .env and set SECRET_KEY (see the comment in that file for how
# to generate one) — DEBUG=True and the rest are already fine for local dev

python manage.py migrate
python manage.py createsuperuser  # creates an ADMIN-role account
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` — you'll be redirected to the login page,
then to the right dashboard based on your account's role.

### Optional: load demo data

```bash
python manage.py seed_demo
```

This creates:

| Role    | Username        | Password              |
|---------|-----------------|------------------------|
| Admin   | `admin`         | `admin12345`           |
| Company | `swiftlogistics`| `swiftlogistics12345`  |

...plus a sample driver, truck, and an in-transit shipment so both
dashboards have something to look at immediately.

**Change these passwords (or delete the seeded accounts) before deploying anywhere real.**

## How the two dashboards interact

1. **Admin registers a company** (`/companies/register/`). This creates a
   `Company` row **and** a linked `User` (role=`COMPANY`) in one step — that
   username/password is what the company uses to sign in.
2. **Admin registers drivers** under that company (`/drivers/register/`).
3. **Company logs in** and lands on `/dashboard/company/`. From there they:
   - Add their own trucks (`/trucks/mine/add/`) — trucks belong to the
     company, not the admin.
   - Create transits (`/transit/mine/new/`), assigning one of their trucks
     (and optionally a driver) to a route.
   - Post tracking updates as the trip progresses — each update is logged
     to a timeline (`TrackingUpdate`) and automatically syncs the truck's
     status/location and the transit's overall status.
4. **Admin can view** all of this read-only: the truck tracking board
   (`/trucks/`) shows every truck's last known location and status across
   every company, and `/transit/` shows every trip network-wide.
5. **Documents**: companies, drivers, and trucks each have their own
   document library (license, insurance, RC/registration, permits, etc.).
   Admin can view all of them; companies can upload documents for their own
   drivers and trucks.

## Deploying

The app reads its configuration from environment variables (see
`.env.example` for the full list), and is set up for a typical gunicorn +
WhiteNoise deployment on a platform like Render, Railway, Fly or Heroku —
anything that reads a `Procfile` and lets you set env vars.

1. **Set environment variables** on the platform (not in a committed file):
   at minimum `SECRET_KEY` (generate a fresh one — don't reuse the local
   dev one in `.env`) and `ALLOWED_HOSTS` (your real domain). Leave `DEBUG`
   unset — it defaults to `False`.
2. **Database**: unset/no `DATABASE_URL` falls back to local SQLite, which
   is fine for a demo but not for real concurrent use. Set
   `DATABASE_URL=postgres://user:password@host:5432/dbname` to switch to
   Postgres (`psycopg2-binary` is already in `requirements.txt`).
3. **Build step** (run on every deploy, before the app starts):
   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```
4. **Start command**: `Procfile` already has `web: gunicorn
   transport_erp.wsgi:application --log-file -` — most platforms pick this
   up automatically.
5. **HTTPS**: `SECURE_SSL_REDIRECT` defaults on whenever `DEBUG=False`, and
   `SECURE_PROXY_SSL_HEADER` is set so it works correctly behind a
   TLS-terminating proxy (which is how all of the platforms above run).
   Once you've confirmed HTTPS works end-to-end on your real domain, turn on
   HSTS by setting `SECURE_HSTS_SECONDS` (see `.env.example` for the
   recommended ramp-up — don't jump straight to a 1-year value).

### What's already handled

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and
  `DATABASE_URL` all come from the environment (`transport_erp/settings.py`,
  via `django-environ`) — nothing secret is hardcoded.
- `DEBUG=False` turns on secure cookies, SSL redirect, and the other
  settings `manage.py check --deploy` looks for.
- Static files are served by WhiteNoise with hashed, cache-busted filenames
  (`manage.py collectstatic` must run on every deploy for this to work).
- Styled `404.html` / `403.html` / `500.html` replace Django's bare default
  error pages once `DEBUG=False`.
- Logging goes to stdout/stderr, which every platform above captures
  automatically — no extra logging infrastructure needed to get started.

### Still worth doing before heavy real-world use

- Put uploaded documents (`MEDIA_ROOT`) on real object storage (S3 or
  similar) — they currently live on local disk, which doesn't survive a
  redeploy on most platforms and isn't shared across multiple instances.
- Add rate limiting / stronger password policy for account creation if
  admins will be enrolling many users.
- Set up real backups for whichever database you deploy with.
- The built-in Django admin is still available at `/django-admin/` for raw
  data operations if you ever need it, separate from the custom dashboards.
