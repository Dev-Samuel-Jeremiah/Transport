"""
Django settings for transport_erp project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Loads variables from a local .env file into the process environment, if one
# exists (it won't on a real deployment — the platform sets real env vars
# instead, and .env is gitignored so it never ships).
environ.Env.read_env(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
# No insecure fallback on purpose — every environment (local dev included)
# must provide its own via .env / the platform's env vars. See .env.example.
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# Defaults to False so a deployment that forgets to set DEBUG fails safe.
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Needed when the site is only ever reached over HTTPS through a domain —
# e.g. https://your-app.onrender.com. Empty by default so local HTTP dev
# isn't affected.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'accounts',
    'companies',
    'drivers',
    'trucks',
    'transit',
    'dashboard',
    'waybills',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'transport_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'transport_erp.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
#
# Defaults to the local SQLite file so `manage.py runserver` keeps working
# with zero setup. Set DATABASE_URL (e.g. postgres://user:pass@host:5432/db)
# in production — psycopg2 is installed and ready for Postgres.

DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# Matches the AutoField every existing table's primary key was already
# created with — this only silences Django's "no default configured"
# warning, it does not change any column type (BigAutoField would, which
# means an unnecessary schema migration across every app for no real
# benefit at this project's scale).
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    # Uploaded documents stay on local disk for now — see README for notes
    # on moving this to object storage (S3 or similar) when that's needed.
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    # WhiteNoise serves static files directly from the app process (no
    # separate nginx/CDN needed to get started) with hashed, cacheable
    # filenames. Run `manage.py collectstatic` as part of every deploy.
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:redirect'
LOGOUT_REDIRECT_URL = 'accounts:login'


# Email
# https://docs.djangoproject.com/en/5.2/topics/email/#topic-email-configuration
#
# Defaults to printing emails to the console, which is what this app uses
# today (it doesn't send any — this is here for whenever it does, e.g. a
# password-reset-by-email flow). Set EMAIL_HOST etc. in production to send
# for real.

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Freightline <no-reply@freightline.local>')


# Logging
# https://docs.djangoproject.com/en/5.2/topics/logging/
#
# Plain console logging — every PaaS (Render, Railway, Heroku, Fly...)
# captures stdout/stderr as logs automatically, so this needs no extra
# infrastructure to be useful in production.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}


# Security — only enforced when DEBUG is off, so local HTTP dev is unaffected.
# https://docs.djangoproject.com/en/5.2/topics/security/
# https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

if not DEBUG:
    # Most hosts (Render, Railway, Heroku, Fly...) terminate TLS at a proxy
    # and forward plain HTTP, with this header marking the original request
    # as HTTPS. Without it, SECURE_SSL_REDIRECT below causes a redirect loop.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # Starts at 0 (off) on purpose: HSTS tells browsers to refuse HTTP for
    # this domain for however many seconds you set, and that's cached
    # client-side — a mistake here isn't quickly reversible. Confirm HTTPS
    # works end-to-end on your real domain first, then raise this via the
    # SECURE_HSTS_SECONDS env var (start with something like 2592000 / 30
    # days, move to 31536000 / 1 year once you're confident).
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
