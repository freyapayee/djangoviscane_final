"""Record security findings in a disposable database; never alter bundled data."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'viscane.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db import connection
from django.test import Client
from django.test.utils import setup_databases, teardown_databases
from core.models import Admin, User, CvScanUpload
from core.services import verify_and_upgrade_password

output = ROOT / '.local'
output.mkdir(exist_ok=True)
results = []
def record(name, safe, actual):
    results.append({'check': name, 'status': 'PASS' if safe else 'FAIL', 'actual': actual})

database = Path(settings.DATABASES['default']['NAME']).resolve()
if database.parent != output.resolve():
    raise SystemExit('Refusing audit: configure database inside .local first.')
with sqlite3.connect(database) as source:
    with sqlite3.connect(output / 'development-backup.sqlite3') as target:
        source.backup(target)
    integrity = source.execute('PRAGMA integrity_check').fetchone()[0]
    tables = [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")]
record('Local SQLite integrity', integrity == 'ok', integrity)
with sqlite3.connect((ROOT / 'db.sqlite3').as_uri() + '?mode=ro', uri=True) as original:
    record('Bundled SQLite integrity (read-only)', original.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Read-only integrity check')

old_config = setup_databases(verbosity=0, interactive=False)
try:
    admin = Admin.objects.create(username='audit-admin', email='admin@example.invalid', role='superadmin',
                                 password_hash=make_password('Audit-only-123!'))
    user = User.objects.create(fullname='Audit Farmer', email='audit@example.invalid', phone='0',
                               password=make_password('Audit-only-123!'))
    anonymous = Client(enforce_csrf_checks=True)
    response = anonymous.post('/superadmin-register', {'username':'untrusted', 'email':'untrusted@example.invalid',
        'password':'Audit-only-123!', 'confirm_password':'Audit-only-123!'})
    created = Admin.objects.filter(username='untrusted', role='superadmin').exists()
    record('Anonymous superadmin registration rejected', not created, f'HTTP {response.status_code}; privileged account created={created}')
    response = anonymous.post('/admin-reset', {'identifier':admin.username, 'email':admin.email,
        'password':'Changed-audit-123!', 'confirm_password':'Changed-audit-123!'})
    admin.refresh_from_db()
    changed = check_password('Changed-audit-123!', admin.password_hash)
    record('Unverified admin password reset rejected', not changed, f'HTTP {response.status_code}; password changed={changed}')
    accepted = verify_and_upgrade_password(user, user.password)
    record('Stored password hash rejected as login password', not accepted, f'Accepted={accepted}')
    client = Client(enforce_csrf_checks=True)
    session = client.session
    session['user_id'] = user.pk
    session['latest_cv_context'] = {'variety':'previous account'}
    session.save()
    response = client.post('/farmer/feedback', {'feedback_message':'CSRF probe'})
    record('Tokenless authenticated mutation rejected', response.status_code == 403, f'HTTP {response.status_code}')
    upload = CvScanUpload.objects.create(user=user, image_path='audit-nonexistent-file.jpg')
    response = client.get(f'/farmer/cv-upload/{upload.pk}/delete')
    deleted = not CvScanUpload.objects.filter(pk=upload.pk).exists()
    record('GET request cannot delete upload', not deleted, f'HTTP {response.status_code}; deleted={deleted}')
    client.get('/logout')
    retained = 'latest_cv_context' in client.session
    record('Logout clears previous prediction context', not retained, f'Context retained={retained}')
    session = client.session
    session['user_id'] = user.pk
    session.save()
    response = client.get('/scan/new')
    scanner_html = response.content.decode('utf-8')
    scanner_connected = '/api/scan/predict?top_k=3' in scanner_html and '/analyze_stalk' not in scanner_html
    record('Legacy scanner uses working prediction endpoint', scanner_connected,
           f'HTTP {response.status_code}; connected={scanner_connected}')
finally:
    teardown_databases(old_config, verbosity=0)

endpoint = urlparse(os.getenv('SCAN_PREDICT_ENDPOINT', 'http://127.0.0.1:8000/predict'))
try:
    with socket.create_connection((endpoint.hostname, endpoint.port or 80), timeout=3):
        predictor = 'TCP reachable; inference still requires a real image test'
except OSError as exc:
    predictor = f'Unavailable: {type(exc).__name__}'
payload = {'django':django.get_version(), 'python':sys.version.split()[0], 'database_tables':tables,
           'prediction_service':predictor, 'results':results}
(output / 'audit-results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
print(json.dumps(payload, indent=2))
