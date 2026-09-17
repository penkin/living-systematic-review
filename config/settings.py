import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-for-deployment")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The tool keeps no user data between runs, so it needs no database. Dropping
# admin, auth and sessions is what makes an empty DATABASES viable. staticfiles
# has no models, so it can stay.
INSTALLED_APPS = ["django.contrib.staticfiles"]
DATABASES = {}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]

STATIC_URL = "static/"
# One built style sheet, web/static/app.css. Rebuild it with `npm run css`.
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]
USE_TZ = True
TIME_ZONE = "Africa/Johannesburg"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# One directory per upload, named by the uuid in the URL. It holds the input CSV,
# the cached model responses, the tags with their confirmed flags, and signals.csv.
RUNS_DIR = Path(os.environ.get("SIGNAL_RUNS_DIR", BASE_DIR / "runs"))

# review.yaml and the rubric are configuration the review team edits without a
# developer present. They are never imported into code.
REVIEW_CONFIG = BASE_DIR / "review.yaml"
REFERENCE_DIR = BASE_DIR / "reference"
RUBRIC_CONFIG = BASE_DIR / "rubric.yaml"

# Committed model responses. A run copies its hits from here, so the demo runs offline.
MODEL_CACHE = BASE_DIR / "cache" / "model"
