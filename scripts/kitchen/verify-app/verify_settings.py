"""Test-only settings. Guards run before Django can open a database connection."""

import os
import re
from urllib.parse import urlparse

db = urlparse(os.environ["DATABASE_URL"])
if (
    not re.fullmatch(
        r"kitchen-verify-[a-f0-9]{12}-[a-f0-9]{12}", os.environ["VERIFY_PROJECT"]
    )
    or (db.scheme, db.hostname, db.port, db.path, db.username)
    != ("postgresql", "verify-db", 5432, "/verify", "verify")
    or db.query
    or db.fragment
    or os.environ["REDIS_URL"] != "redis://verify-redis:6379/0"
):
    raise RuntimeError("Refusing non-disposable database/project/cache")

from plane.settings.common import *

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "api"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_BROKER_URL = "redis://verify-redis:6379/1"
STATIC_ROOT = "/runtime/static"
MEDIA_ROOT = "/runtime/media"
