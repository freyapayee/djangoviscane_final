# Local Windows execution

Verified on Python 3.11.9 and Django 5.2.17. The Django checkout is independent
of the parent Flask project. Its virtual environment is `../.venv-django`.
`requirements-windows.lock.txt` records the verified application and browser-test
dependencies; the source repository did not provide an exact environment lock.

## Start the configured installation

From the parent `visane-app` workspace:

```powershell
.\djangoviscane_final\start-local.ps1
```

Or, without a PowerShell script:

```powershell
Set-Location .\djangoviscane_final
..\.venv-django\Scripts\python.exe manage.py runserver 127.0.0.1:5000 --noreload
```

Open http://127.0.0.1:5000/. If the server from the execution review is still
running, use it rather than starting a second process on the same port.
Use Ctrl+C in its terminal to stop a foreground server. `start-local.ps1 -Port 5001`
starts on an alternate port. The browser verification scripts expect port 5000.

## Local configuration and data

- `.env.local`: generated random secret, localhost-only hosts, debug enabled,
  absolute SQLite path, and the repository's prediction API endpoint.
- `.local/development.sqlite3`: newly initialized local database.
- `db.sqlite3`: original bundled database, preserved unchanged.
- `.local/browser-test-accounts.json`: synthetic QA farmer/admin credentials;
  private and ignored by Git. These accounts exist only in the local database.
- `.local/*.json` and `.local/browser-*.png`: verification evidence.
- `static/uploads/cv_scans/`: images written by the application, including the
  public sample used for the live prediction check. New uploads are ignored.

Keep `.env.local`, `.local/`, and the parent `.venv-django/` out of commits.
The parent project does not currently ignore `.venv-django/`; do not stage it.
The Django folder has its own Git repository and remote. Do not accidentally
commit it to the parent as an embedded repository.

The configured prediction endpoint is `http://52.74.98.121:8010/predict`, as
defined by this repository. It was live-tested successfully. It uses HTTP;
replace it with a trusted HTTPS endpoint before sending sensitive images.
Restart Django after changing `.env.local` because startup uses `--noreload`.
DeepSeek is optional and was not configured: local Hiligaynon translations work
without an API key. Live DeepSeek requests were not tested.

## Recreate the environment

From the parent workspace, with a working Python 3.11 installation:

```powershell
python -m venv .venv-django
.\.venv-django\Scripts\python.exe -m pip install --only-binary=:all: -r .\djangoviscane_final\requirements-windows.lock.txt
Set-Location .\djangoviscane_final
```

Create `.local/`, copy `.env.example` to `.env.local`, and uncomment/configure
the settings. Generate a random secret rather than using the example text.
The checked-in example deliberately contains comments only: the current settings
loader does not correctly override values loaded from an earlier environment
file. Define actual values in `.env.local` or the process environment.

Then run:

```powershell
..\.venv-django\Scripts\python.exe manage.py check
..\.venv-django\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv-django\Scripts\python.exe manage.py migrate
..\.venv-django\Scripts\python.exe manage.py collectstatic --noinput
..\.venv-django\Scripts\python.exe manage.py test core
```

The Microsoft Store Python interpreter required execution outside the Codex
sandbox during this review. It works from the normal Windows environment.

## Repeat verification

```powershell
..\.venv-django\Scripts\python.exe scripts/audit_local.py
..\.venv-django\Scripts\python.exe scripts/browser_verify.py
..\.venv-django\Scripts\python.exe scripts/verify_live_prediction.py
..\.venv-django\Scripts\python.exe scripts/backup_local.py
```

The audit uses a disposable database for security probes and writes findings;
its successful execution does NOT mean the security checks passed. Read
`.local/audit-results.json`.
Browser checks use installed Microsoft Edge, create synthetic local accounts,
and add QA data. The live prediction script sends the public repository sample
`static/varieties/vmc-84-524.jpg` to the configured external service.
The backup utility creates and verifies a timestamped local SQLite snapshot.
Back up uploaded files separately; a database snapshot does not contain images.

## Android and production integration

The existing Android WebView defaults to `http://10.0.2.2:5000/`. This matches
the Django port for an Android emulator; device connectivity was not tested.
Physical-phone access needs a deliberate LAN binding, allowed-host entry,
firewall configuration and preferably HTTPS. The current localhost binding is
intentional while the unresolved security findings remain.

Do not point Django migrations at the existing Flask database. Table names
overlap, but migration history, ID types, lengths, sessions, and authentication
behavior differ. Rehearse any data transfer on a backed-up copy first.

Docker execution was not tested. Compose currently uses a development server,
shares container naming with the parent project, and does not run migrations
before startup. Read `DJANGO_EXECUTION_REPORT.md` before deployment.
