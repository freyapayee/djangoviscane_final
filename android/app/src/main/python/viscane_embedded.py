import importlib
import os
import sys
import threading
from pathlib import Path

_server = None
_server_lock = threading.Lock()


def start(project_root, database_path, secret_key):
    global _server
    with _server_lock:
        if _server is not None:
            return _server.server_port

        root = Path(project_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(root))
        os.environ["DJANGO_SETTINGS_MODULE"] = "viscane.settings"
        os.environ["VISCANE_SECRET_KEY"] = secret_key
        os.environ["DJANGO_DEBUG"] = "true"
        os.environ["DJANGO_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
        os.environ["VISCANE_FARMER_ONLY"] = "true"
        os.environ["VISCANE_OFFLINE"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(database_path).resolve())
        os.environ["VISCANE_PRIVATE_UPLOAD_ROOT"] = str(root / "private")

        project_settings = importlib.import_module("viscane.settings")
        project_settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(Path(database_path).resolve()),
                "OPTIONS": {"timeout": 20},
            }
        }
        project_settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
        project_settings.FARMER_ONLY = True
        project_settings.DEBUG = True
        project_settings.SECRET_KEY = secret_key
        project_settings.SECURE_SSL_REDIRECT = False
        project_settings.SESSION_COOKIE_SECURE = False
        project_settings.CSRF_COOKIE_SECURE = False
        project_settings.TEMPLATES[0]["DIRS"] = [root / "templates"]
        project_settings.STATICFILES_DIRS = [root / "static"]
        project_settings.MEDIA_ROOT = root / "media"
        project_settings.PRIVATE_UPLOAD_ROOT = root / "private"
        (root / "media").mkdir(parents=True, exist_ok=True)
        (root / "private").mkdir(parents=True, exist_ok=True)

        import django
        django.setup()
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from wsgiref.simple_server import WSGIRequestHandler, make_server

        call_command("migrate", interactive=False, verbosity=0)
        application = StaticFilesHandler(get_wsgi_application())

        class QuietRequestHandler(WSGIRequestHandler):
            def log_message(self, format, *args):
                pass

        _server = make_server("127.0.0.1", 0, application, handler_class=QuietRequestHandler)
        threading.Thread(target=_server.serve_forever, name="viscane-django", daemon=True).start()
        return _server.server_port
