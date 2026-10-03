# Django Project Execution Report

Reviewed locally on 27 September 2026. Repository:
https://github.com/freyapayee/djangoviscane_final
Commit: `41d3654f4faad70090fc35c5b2ab5daa0e61febc`.

## 1. Repository Analysis

**Purpose:** VISCANE farmer and administrator portal for sugarcane image
classification, agronomic estimates, recommendations, scan history and reports.

**Architecture:** Django routes/views, custom session-based authentication,
Django ORM, Jinja2 server-rendered templates, shared static assets, a local
agronomic calculation service, and a separate image-classification API.
The project does not use Django's standard User model/admin application.

Installed applications are `django.contrib.sessions`,
`django.contrib.staticfiles`, and `core`. Models include User, Admin, Scan,
AuditLog, SystemConfig, Notification, Feedback, AgronomicLog and CvScanUpload.
`core/migrations/0001_initial.py` describes the application schema.

`core/views.py` handles requests; `core/services.py` contains prediction,
password migration and persistence helpers; `core/language.py` contains local
Hiligaynon translations plus optional DeepSeek translation. `viscane/jinja2.py`
adapts existing Flask-style `url_for` calls to Django routing.

Templates and static assets are project-level directories. Media settings
exist, but CV uploads currently go to `static/uploads/cv_scans`, not MEDIA_ROOT.
The URL configuration does not serve MEDIA_ROOT itself.

External dependencies include the image API, optional DeepSeek, Google Fonts,
Ionicons, and weather/geolocation functionality. The external image-model code
and weights are not included, so their original training environment was not
reproduced. Local yield estimates use weighted baselines and scikit-learn.

## 2. Environment Setup Status

**Local environment prepared and running.**

- Python 3.11.9, dedicated `../.venv-django` environment.
- Django 5.2.17, Jinja2 3.1.6, scikit-learn 1.8.0.
- `.env.local` contains a generated random secret, local allowed hosts, an
  isolated SQLite path, and the repository's working prediction endpoint.
- Server: http://127.0.0.1:5000/.
- Restart instructions: `WINDOWS_SETUP.md` and `start-local.ps1`.

The README references Python 3.14 from another installation; Docker specifies
3.11. This review verifies 3.11.9, not an exact reconstruction of an undocumented
original environment. A version lock now records the verified Windows setup.

The initial Git transfer stalled. A shallow fetch over HTTP/1.1 completed and
checked out the requested commit. Microsoft Store Python required execution
outside the Codex sandbox. Browser-tool download initially timed out and then
succeeded with a longer timeout. No system Python packages were modified.

## 3. Dependency Status

All application requirements installed successfully from binary wheels.
`pip check` reported **No broken requirements found** before the separate
browser-test tool installation. Jinja2 was missing from the original manifest
despite the configured template backend; `Jinja2>=3.1,<4` was added.

`requirements-windows.lock.txt` records exact installed versions, including
Playwright test tooling. Production application dependencies remain in
`requirements.txt`. The optional OpenAI-compatible SDK is used for DeepSeek;
no API key was configured and no paid translation request was made.

The original repository also contains `requirements 2.txt`, `Dockerfile 2`,
and `docker-compose 2.yml`. These alternate copies are not used by this setup
and can confuse future maintenance.

## 4. Database Status

**PASS for the new local SQLite database.**

- `makemigrations --check --dry-run`: no changes detected.
- `makemigrations`: no changes detected; no migration file generated.
- `migrate --noinput`: core.0001_initial and sessions.0001_initial applied.
- `showmigrations`: both migrations marked applied.
- Nine application tables, Django migration/session tables, and SQLite's
  sequence table present.
- SQLite integrity check: `ok`.
- Original bundled `db.sqlite3`: read-only integrity check passed and Git
  confirms it remains unchanged.
- Timestamped backup of the post-browser-test local database created and
  verified under `.local/backups/` using SQLite's online backup API.

Original database SHA-256:
`30A790AD90E13D80D9D1E55E44B2C613C2E43DD1173CFB6A17183355EB2912D7`.

No existing Flask/PostgreSQL data was migrated or changed. PostgreSQL execution
and production backup restoration were not tested. Image files need their own
backup in addition to the database snapshot.

## 5. Execution Status

- `manage.py check`: **0 issues**.
- `manage.py test core`: **25 tests passed** (6 existing language tests and
  19 added execution/security tests).
- `collectstatic --noinput`: **40 files copied**.
- Live homepage and stylesheet: **HTTP 200**.
- Headless Edge: **12 browser checks passed**, no JavaScript page exceptions.
- Live prediction: **HTTP 200**, response rendered and scan persisted.

`agent-browser` was not installed, so browser verification used Playwright with
installed Microsoft Edge. Screenshots were inspected, including the mobile
layout. Screenshot animations were disabled to avoid capturing partially
transparent entrance animations.

The server is intentionally bound to localhost. It has not been deployed or
tested on an Android emulator/physical device.

## 6. Functional Testing Results

| Feature | Expected result | Actual result | Status |
|---|---|---|---|
| Farmer registration | Save account and show success | Browser form reached success page | PASS |
| Farmer login/logout | Authenticate and restrict protected pages after logout | Browser and Django tests passed for identity removal | PASS; residual context issue below |
| Archived/inactive permissions | Reject inactive login and unauthenticated access | Inactive login/protected-route tests passed | PASS for tested cases |
| Farmer pages | Render home, recommendations, logs, settings | HTTP 200 and browser content | PASS |
| Admin setup | Create first administrator locally | Browser reached dashboard | PASS functional; provisioning risk remains |
| Farmer CRUD/search | Create, search, edit, deactivate, reactivate | Database assertions and browser creation passed | PASS |
| Admin POST forms | Submit with CSRF token | Tokens added; enforced-CSRF test and browser passed | FIXED |
| Scan validation | Reject maturity >100; store valid value | Invalid rejected, valid stored | PASS |
| Agronomic calculation | Produce and persist estimate | Non-null estimate persisted | PASS execution; scientific validity not certified |
| Feedback | Persist submitted message | Correct form field persisted | PASS |
| Reports/export | Render pages and return CSV | Admin/superadmin pages and CSV passed | PASS rendering; unit-label concerns below |
| Upload ownership | User cannot delete another user's upload | Other user's record retained | PASS |
| Owner deletion | Remove owned image and record | Temporary image and row removed | PASS |
| Prediction validation | Reject missing upload, bad top_k, bad JSON | 400/502 as expected | PASS |
| Prediction outage | Return actionable error | Mocked unreachable service produced 502 | PASS error path |
| Live CV integration | Browser -> Django -> external API -> database -> UI | Full real flow succeeded | PASS integration |
| Hiligaynon | Preserve machine values, numbers and original advice | All 6 original tests passed | PASS tested local/mocked behavior |
| DeepSeek live translation | Real API translation | No key configured | NOT TESTED |
| Physical camera/Android | Capture and upload from hardware | No device test | NOT TESTED |
| Privileged provisioning | Reject anonymous creation/reset; allow authorized superadmin | Regression and CSRF tests passed | FIXED |
| Upload deletion | Reject GET; accept authorized CSRF-protected POST | 405 on GET; owner POST test passed | FIXED |
| Legacy scanner | Send captured image to supported prediction route | Uses `/api/scan/predict`; template contract test passed | FIXED |

The live sample was the public repository asset `static/varieties/vmc-84-524.jpg`.
The API combined resnet18 and yolov8 and returned `847__Mature`, normalized to
VMC 84-947, at 0.338307619 confidence. The UI displayed 33.8% and the image and
record were confirmed on disk/in SQLite. This is a connectivity/contract test,
not ground-truth validation; the filename alone does not establish a label.

Evidence: `.local/browser-results.json`, `.local/live-prediction-results.json`,
`.local/audit-results.json`, and `.local/browser-*.png`. The audit JSON's earlier
localhost prediction availability entry is superseded by the successful live
prediction report after restoring the repository endpoint.

## 7. Errors Found and Solutions

### Setup/runtime fixes completed

| File | Original problem | Change and reason |
|---|---|---|
| requirements.txt | Jinja2 omitted | Declare template-engine dependency for clean installs |
| .env.example | Referenced file absent | Add documented, commented configuration template |
| .env.local (ignored) | No isolated local configuration | Generate secret and configure isolated database/working prediction API |
| templates/admin_farmers.html | Four POST forms omitted CSRF input | Add tokens so protected views accept real browser submissions |
| templates/admin_farmer_edit.html | POST form omitted CSRF input | Add token and verify edit with CSRF enforcement |
| .gitignore | Generated local evidence/uploads not excluded | Ignore .local, collected static, local venvs and new uploads |

Added repeatable tests, audit/browser/backup scripts, a Windows dependency lock,
and startup documentation. No existing feature was removed and no backend
architecture, original database, or parent Flask/Android source was replaced.

### Critical findings resolved on 28 September 2026

| Original finding | Resolution |
|---|---|
| Anonymous admin/superadmin registration | Both routes now require an authenticated superadmin and CSRF token; first-admin setup remains available only while no active admin exists |
| Identifier/email-only admin reset | Reset now requires an authenticated superadmin, CSRF token and minimum eight-character replacement password |
| GET-based upload deletion | Endpoint now accepts POST only, is no longer CSRF-exempt, and the form includes `csrf_input` |
| Broken `/analyze_stalk` scanner call | Legacy scanner now posts to the verified `/api/scan/predict?top_k=3` route and reports response errors/results |

### Confirmed unresolved findings

Security probes ran only against a disposable Django test database.

| Priority | Location | Evidence/problem | Proposed solution |
|---|---|---|---|
| High | core/services.py:835 | Password verifier accepts stored hash as submitted password | Remove unrestricted plaintext equality; explicitly migrate identified legacy records |
| High | core/views.py:241,510 and other csrf_exempt views | Authenticated tokenless feedback accepted | Add tokens/headers and remove exemptions from mutations |
| High | core/views.py:590 | Shared temporary reset password is exposed in redirect query | Unique expiring recovery mechanism; no secrets in URLs |
| Medium | core/views.py:1041 | Logout retains latest_cv_context | Flush/rotate session and clear user-scoped state |
| Medium | templates/scan_new.html:187 | Calls absent /analyze_stalk; fetch ignores HTTP error status | Integrate existing prediction API and render valid/error responses |
| Medium | viscane/settings.py:14 | Environment loader recaptures existing keys per file, preventing intended later overrides | Capture process-original keys once; test documented precedence |
| Medium | core/services.py:374; core/views.py:1127 | Area-scaled tonnage retained under TC/HA name and exported as LKG/HA | Define and consistently calculate units, migrate report labels |
| Medium | core/views.py:1073 | Maintenance/model upload settings saved but not wired to enforcement/inference | Implement stated effects or accurately label administrative controls |
| Medium | core/views.py:532 | Backup/login events and 68% storage utilization are hardcoded | Use measured operational data or label demo placeholders |

Other static risks: weak server-side numeric bounds; swallowed persistence
errors; public static upload URLs; no upload image-content/size validation;
missing actor relationships for audit/feedback; bulk unpaginated reports;
and default HTTP transport for prediction. The repository tracks a private
certificate key and a populated database. Their contents were not reproduced.
Rotate the key if still trusted and review whether bundled data may be shared.

Browser diagnostics: `/favicon.ico` returned 404; Google Fonts CSS requests
were blocked with `ERR_BLOCKED_BY_ORB`. Local CSS/images loaded and fallback
fonts rendered. These warnings were recorded, not hidden. A server broken-pipe
message occurred when an HTTP-check client closed a response connection.

## 8. Code Quality Review

The Django conversion improves separation through models/services/views and
uses migrations. Several reports use select_related/aggregates. The prediction
adapter validates JSON and recognizable predictions before reporting success.
Language tests preserve numeric advice and domain terminology.

Remaining concerns are custom authentication without full session lifecycle
management, large views/services modules, inconsistent method restrictions,
numeric data stored in strings, and silent exception handling. Foreign-key
relations exist for scans/logs/uploads, but several actor IDs are bare integers.
Database-level domain constraints are limited. Performance benchmarks and
concurrency/load testing were not performed.

`check --deploy` reported five warnings: missing HSTS, missing HTTPS redirect,
non-secure session cookie, non-secure CSRF cookie, and DEBUG enabled. These are
documented development settings, not a production approval. Docker also uses
runserver and lacks a migration startup step. Its .dockerignore does not fully
exclude local secrets, databases, and key files.

Production should use an appropriate WSGI/ASGI server, HTTPS, restricted hosts,
secure cookies, configured static/media serving, protected secrets, and tested
backup restoration. Django explicitly excludes runserver from production use:
[Django deployment checklist](https://github.com/django/django/blob/main/docs/howto/deployment/checklist.txt).
The CSRF template fix follows Django's documented Jinja2 mechanism:
[Django CSRF documentation](https://github.com/django/django/blob/main/docs/howto/csrf.txt).

## 9. Integration Recommendations

Integration completed as an independent checkout plus runnable local server,
environment, tests and startup script inside the current workspace. This
provides a working Django application without overwriting the parent Flask app.

The existing Android WebView's emulator URL uses port 5000, matching this server.
No Android rewrite is needed to load the Django web UI. Emulator and physical
device tests remain necessary, especially camera permissions, uploads, cookies,
downloads and lifecycle behavior. Physical-device/LAN exposure is not enabled.

Do not merge Django migrations directly into the Flask database. Despite shared
table names, migration history, primary-key types, field lengths, password
formats and session storage differ. Plan a backed-up, rehearsed import with
row counts, relationship validation and password compatibility checks.

Keep parent Flask files, Android sources and original databases unchanged until
a deliberate cutover is selected. The nested checkout has its own Git history.
The parent `.venv-django` is an untracked environment and must not be committed.

## 10. Final Status

**REQUIRES MAJOR FIXES for production readiness and complete feature/security
acceptance.**

**Local execution is operational:** Django starts, migrations match, 25 tests
pass, browser workflows work, and real image prediction is integrated and saved.
The four requested critical issues are fixed. Remaining high and medium findings
still prevent production certification. DeepSeek, physical camera/Android, PostgreSQL,
Docker deployment and scientific model accuracy remain outside verified scope.

The current checkout is suitable for controlled local review of the verified
flows. Resolve the remaining password-compatibility, CSRF, reset-secret and
deployment-hardening findings before enabling wider access. Correct report units
and complete model validation before making thesis accuracy claims.
