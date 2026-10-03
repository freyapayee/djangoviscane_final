# VISCANE Final Run Checklist

Use PowerShell from the parent `visane-app` workspace. The verified environment
is Python 3.11.9 with Django 5.2.17. Keep the Django application bound to
localhost during preparation because production hardening is still pending.

## 1. Install

For the already prepared workspace:

```powershell
.\.venv-django\Scripts\python.exe --version
.\.venv-django\Scripts\python.exe -m pip install --only-binary=:all: -r .\djangoviscane_final\requirements-windows.lock.txt
.\.venv-django\Scripts\python.exe -m pip check
```

For a fresh workspace, create the environment first:

```powershell
python -m venv .venv-django
.\.venv-django\Scripts\python.exe -m pip install --only-binary=:all: -r .\djangoviscane_final\requirements-windows.lock.txt
```

Expected: Python 3.11.x and `No broken requirements found`.

## 2. Configure

```powershell
Copy-Item .\djangoviscane_final\.env.example .\djangoviscane_final\.env.local
New-Item -ItemType Directory -Force .\djangoviscane_final\.local
```

Edit `.env.local` and set real values. Use an absolute path with forward slashes:

```env
VISCANE_SECRET_KEY=<new-random-secret>
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,testserver
DATABASE_URL=sqlite:///C:/absolute/path/to/djangoviscane_final/.local/development.sqlite3
SCAN_PREDICT_ENDPOINT=http://52.74.98.121:8010/predict
SCAN_PREDICT_TIMEOUT_SECONDS=30
```

Generate a secret without printing it into source control:

```powershell
.\.venv-django\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the result into the ignored `.env.local`. Never commit that file.

## 3. Check and migrate the database

```powershell
Set-Location .\djangoviscane_final
..\.venv-django\Scripts\python.exe manage.py check
..\.venv-django\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv-django\Scripts\python.exe manage.py migrate --noinput
..\.venv-django\Scripts\python.exe manage.py showmigrations
..\.venv-django\Scripts\python.exe manage.py test core
..\.venv-django\Scripts\python.exe manage.py collectstatic --noinput
```

Expected: zero system-check issues, no model changes, core/session migrations
marked `[X]`, 25 tests passing, and static collection completing.

## 4. Run the server

From the parent workspace:

```powershell
.\djangoviscane_final\start-local.ps1
```

Or from `djangoviscane_final`:

```powershell
..\.venv-django\Scripts\python.exe manage.py runserver 127.0.0.1:5000 --noreload
```

Open http://127.0.0.1:5000/. Keep this terminal open. Stop with Ctrl+C.
Use `/admin-setup` only when the database has no active administrator. Once the
first account exists, only an authenticated superadmin can create or reset
administrator accounts.

## 5. Test the demonstration workflow

Manual sequence:

1. Register a farmer and log in.
2. Open the farmer dashboard and verify CSS/images.
3. Use **Upload Photo** with a JPG/PNG sugarcane image.
4. Confirm variety, maturity, and AI score appear.
5. Complete agronomic fields and calculate the estimate.
6. Open recommendations and agronomic logs.
7. Log out and verify the dashboard redirects to login.
8. Log in as superadmin; check farmers, monitoring, reports, communications and audit pages.

Automated browser and live-prediction checks require the server on port 5000:

```powershell
..\.venv-django\Scripts\python.exe scripts\browser_verify.py
..\.venv-django\Scripts\python.exe scripts\verify_live_prediction.py
```

The live script sends the repository's public sample image to the configured
external API. A successful request verifies integration, not scientific accuracy.

## 6. Back up before the demonstration

```powershell
..\.venv-django\Scripts\python.exe scripts\backup_local.py
Copy-Item -Recurse .\static\uploads .\.local\backups\uploads
```

The script creates an integrity-checked, timestamped SQLite snapshot. Copy
uploads separately because image files are not inside the database.

## 7. Final five-minute check

- Laptop charger connected and sleep disabled.
- Network reaches `http://52.74.98.121:8010/health` or `/docs`.
- Server terminal shows no traceback.
- A known local image is available if camera permission fails.
- English/Hiligaynon selector renders correctly.
- Test farmer and superadmin credentials are available privately.
- Backup exists and opens.
- Android emulator uses `http://10.0.2.2:5000/`; physical-device LAN use needs separate secure configuration.

If the prediction service is unavailable, explain that agronomic calculation is
local but image classification is an external dependency. Do not claim that an
API confidence score is measured model accuracy.
