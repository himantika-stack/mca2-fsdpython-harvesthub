from pathlib import Path
import os
import sys
import urllib.parse
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")

secret_key_env = os.getenv("DJANGO_SECRET_KEY")
if not secret_key_env:
    if DEBUG:
        SECRET_KEY = "harvesthub-development-insecure-secret-key-replace-in-production"
    else:
        SECRET_KEY = get_random_secret_key()
else:
    SECRET_KEY = secret_key_env

raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
for default_host in ["localhost", "127.0.0.1", ".onrender.com", ".vercel.app"]:
    if default_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(default_host)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "farm",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "harvesthub.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "harvesthub.wsgi.application"

# Database configuration: support DATABASE_URL/MYSQL_URL or discrete MYSQL_* variables.
db_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
if db_url:
    parsed_url = urllib.parse.urlparse(db_url)
    db_name = parsed_url.path.lstrip("/") or "test"
    db_user = urllib.parse.unquote(parsed_url.username or "")
    db_password = urllib.parse.unquote(parsed_url.password or "")
    db_host = parsed_url.hostname or ""
    db_port = str(parsed_url.port or (4000 if "tidb" in db_host.lower() else 3306))
else:
    db_host = os.getenv("MYSQL_HOST", "")
    default_port = "4000" if (db_host and "tidb" in db_host.lower()) else "3306"
    db_port = os.getenv("MYSQL_PORT", default_port)
    db_name = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQL_DB") or "test"
    db_user = os.getenv("MYSQL_USER", "")
    db_password = os.getenv("MYSQL_PASSWORD", "")

missing_mysql = []
if not db_host:
    missing_mysql.append("MYSQL_HOST")
if not db_user:
    missing_mysql.append("MYSQL_USER")

if missing_mysql and not any(arg in {"test", "makemigrations", "collectstatic"} for arg in sys.argv):
    raise RuntimeError("MySQL configuration is required. Set " + ", ".join(missing_mysql) + " or DATABASE_URL in environment variables.")

mysql_options = {"charset": "utf8mb4"}
use_ssl = (
    os.getenv("MYSQL_SSL", "False").lower() in ("true", "1", "yes")
    or (db_host and any(cloud in db_host.lower() for cloud in ["tidbcloud.com", "aivencloud.com", "aws.com", "rds.amazonaws.com"]))
)
if use_ssl:
    mysql_options["ssl"] = {"ssl_mode": "REQUIRED"}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "HOST": db_host,
        "PORT": db_port,
        "OPTIONS": mysql_options,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS and CSRF Origins
raw_origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
for local_dev in ["http://localhost:5173", "http://127.0.0.1:5173"]:
    if local_dev not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(local_dev)

CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)
for trusted in ["https://*.vercel.app", "https://*.onrender.com", "http://localhost:5173", "http://127.0.0.1:5173"]:
    if trusted not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(trusted)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.onrender\.com$",
]
CORS_ALLOW_CREDENTIALS = True

# Security and Cookies
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "yes")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}
