"""ASGI config for VISCANE."""

import os

from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viscane.settings")
application = get_asgi_application()
