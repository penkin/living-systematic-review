import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

# Keys live in a git-ignored .env; the shell wins so a deploy can override the file.
if (BASE_DIR / ".env").is_file():
    for line in (BASE_DIR / ".env").read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip("'\""))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-for-deployment")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No admin, auth or sessions: nobody logs in, and CSRF works from a cookie alone.
INSTALLED_APPS = ["web", "django.contrib.staticfiles"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.environ.get("SIGNAL_DB", BASE_DIR / "db.sqlite3")),
        # WAL lets the refreshing run page read while the tagging thread writes.
        # The timeout makes a confirm during tagging wait instead of failing on the lock.
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE", "init_command": "PRAGMA journal_mode=WAL;"},
    }
}

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

# review.yaml and the rubric are configuration the review team edits without a
# developer present. They are never imported into code.
REVIEW_CONFIG = BASE_DIR / "review.yaml"
REFERENCE_DIR = BASE_DIR / "reference"
RUBRIC_CONFIG = BASE_DIR / "rubric.yaml"

