# Final Project Status Report

Date: 28 September 2026  
Repository commit reviewed: `41d3654f4faad70090fc35c5b2ab5daa0e61febc`

## 1. Django Implementation Status

The Django application is operational in the prepared Windows workspace. It
uses Django 5.2.17 on Python 3.11.9, Jinja2 templates, Django ORM, an isolated
SQLite demonstration database and the repository-configured remote prediction
service. It preserves the original farmer, administrator, recommendation,
reporting, localization and computer-vision workflows.

Completed work:

- Added the missing Jinja2 dependency and exact verified Windows lock file.
- Added safe example/local environment guidance and a localhost startup script.
- Initialized and migrated a separate SQLite database; preserved the bundled database.
- Added repeatable execution, browser, live-prediction, audit and backup scripts.
- Added CSRF tokens to the previously broken administrator farmer forms.
- Restricted admin and superadmin creation to an authenticated superadmin.
- Restricted administrator password reset to an authenticated superadmin with CSRF protection.
- Changed CV upload deletion to a CSRF-protected POST-only action.
- Connected the legacy scan page to the verified prediction endpoint with response handling.
- Added regression coverage for every critical fix.
- Added final run, Android migration and thesis documentation.

## 2. Testing Results

| Verification | Result |
|---|---|
| `manage.py check` | PASS, no issues |
| Migration drift | PASS, no changes detected |
| Database migration | PASS, core and sessions applied |
| Automated tests | PASS, 25/25 |
| Dependency consistency | PASS, no broken requirements |
| Static collection | PASS, 40 files |
| Local server | PASS, HTTP 200 |
| Browser flows | PASS, registration/login/logout/farmer/admin workflows |
| Live prediction | PASS, browser → Django → classifier → database/UI |
| SQLite integrity and backup | PASS |

The live prediction was a smoke test using a repository asset. The returned
33.8% score is per-image confidence, not measured model accuracy.

## 3. Security Status

The four requested critical issues are resolved and covered by automated tests.
The system is safer for a controlled thesis demonstration but is not approved
for public production access.

### Remaining issue 1

**Issue:** Stored password-hash text can be accepted as a submitted password by
the legacy migration fallback.  
**Severity:** High  
**Location:** `core/services.py`, `verify_and_upgrade_password`  
**Impact:** Disclosure of a stored legacy/Django hash could permit authentication
without recovering the original password.  
**Recommended fix:** Inventory actual legacy password formats, mark accounts that
require migration, and remove unrestricted plaintext equality after a controlled
password-reset campaign.

### Remaining issue 2

**Issue:** Multiple state-changing views remain `csrf_exempt`.  
**Severity:** High  
**Location:** `core/views.py`, including farmer feedback, calculation, account
login/setup and several administrator mutation routes  
**Impact:** A signed-in browser may be induced to submit unauthorized changes.  
**Recommended fix:** Add `csrf_input` to all Jinja2 forms, add the CSRF header to
same-origin fetch requests, then remove exemptions one workflow at a time with
enforced-CSRF tests.

### Remaining issue 3

**Issue:** Farmer reset uses shared password `12345` and places it in a redirect URL.  
**Severity:** High  
**Location:** `core/views.py`, `admin_farmers` reset action  
**Impact:** Predictable credentials and secrets may leak through history, logs or
screenshots.  
**Recommended fix:** Generate a single-use expiring recovery token, require a new
password at first use, and never place credentials in URLs.

### Remaining issue 4

**Issue:** No authentication rate limiting or lockout controls were found.  
**Severity:** High  
**Location:** Farmer/admin/superadmin login and setup routes  
**Impact:** Password guessing and resource abuse are not meaningfully constrained.  
**Recommended fix:** Add per-account/IP throttling with careful proxy-IP handling,
generic errors, audit events and temporary backoff.

### Remaining issue 5

**Issue:** Uploads lack strict server-side size, MIME and decoded-image validation.  
**Severity:** High  
**Location:** `core/views.py:api_scan_predict`, `core/services.py` persistence  
**Impact:** Large or malformed files can consume memory/storage or be publicly
served from a static directory.  
**Recommended fix:** Set request/file limits, decode and verify supported images,
store private media outside static assets, and serve it through authorized views
or protected object storage.

### Remaining issue 6

**Issue:** Prediction traffic uses plain HTTP.  
**Severity:** High for deployed/sensitive use  
**Location:** `SCAN_PREDICT_ENDPOINT` and `core/services.py` default endpoint  
**Impact:** Images and results can be observed or modified in transit.  
**Recommended fix:** Put the prediction service behind authenticated HTTPS and
pin its trusted hostname/configuration in deployment secrets.

### Remaining issue 7

**Issue:** Logout removes only the principal ID and retains prediction/recommendation context.  
**Severity:** Medium  
**Location:** `core/views.py`, `logout` and `admin_logout`  
**Impact:** State from a prior account can persist in a shared-browser session.  
**Recommended fix:** Flush or rotate the session and explicitly clear all
principal-scoped keys on login and logout.

### Remaining issue 8

**Issue:** Environment-file precedence does not behave as documented.  
**Severity:** Medium  
**Location:** `viscane/settings.py`, `load_env_file`  
**Impact:** Example/default values can unexpectedly prevent local overrides.  
**Recommended fix:** Capture process-originated keys once before loading files,
then test `.env.example < .env.local < process environment` precedence.

### Remaining issue 9

**Issue:** Maintenance mode and uploaded model configuration are stored without
controlling requests or inference.  
**Severity:** Medium  
**Location:** `core/views.py:superadmin_settings`, `core/services.py`  
**Impact:** The interface implies operational effects that do not occur.  
**Recommended fix:** Implement reviewed middleware/model activation or relabel
these controls as demonstration metadata.

## 4. Remaining Quality and Performance Issues

### Remaining issue 10

**Issue:** Measurement names mix per-hectare and area-scaled totals.  
**Severity:** High for thesis validity  
**Location:** `core/services.py:predict_variety_metrics`, report views/templates  
**Impact:** Reported TC/HA, total tonnage and LKG/HA can be interpreted incorrectly.  
**Recommended fix:** Define a unit dictionary with domain advisers, rename every
field, calculate each quantity once and migrate reports/tests together.

### Remaining issue 11

**Issue:** Prediction/report queries can load full datasets and some relations
are represented as bare integer actor IDs.  
**Severity:** Medium  
**Location:** Report, communications and audit views; Feedback/AuditLog/Notification models  
**Impact:** Response time and memory usage grow with data; referential integrity
and efficient joins are limited.  
**Recommended fix:** Paginate, aggregate in SQL, add indexes based on measured
queries, use proper relationships where actor identity is unambiguous, and load-test.

### Remaining issue 12

**Issue:** Several persistence and translation exceptions are swallowed.  
**Severity:** Medium  
**Location:** `core/services.py`, calculation/prediction persistence paths  
**Impact:** Users may see apparent success while storage or translation failed.  
**Recommended fix:** Add structured logs, user-safe error states, transaction
boundaries and monitoring without exposing secrets or raw personal data.

### Remaining issue 13

**Issue:** Operational dashboard events and 68% storage use are hardcoded.  
**Severity:** Medium  
**Location:** `core/views.py:admin_portal`  
**Impact:** Thesis evaluators may interpret demonstration placeholders as measured data.  
**Recommended fix:** Connect them to actual metrics or visibly label them sample data.

## 5. Production Readiness

**Status: ready for controlled local thesis rehearsal with minor operational
preparation; not production-ready.**

Fresh installation, requirements, environment documentation, database setup,
server startup, prediction communication, static files, upload persistence and
core user workflows have been verified. Exact commands are in
`FINAL_RUN_CHECKLIST.md`.

Production blockers include the remaining high-risk security findings, five
`check --deploy` warnings (HSTS, HTTPS redirect, secure session/CSRF cookies and
debug mode), use of Django `runserver`, permissive hosts in defaults, public
upload storage, untested PostgreSQL/Docker recovery, and no production monitoring.

## 6. Android Conversion Blueprint

The complete feature inventory, Django-to-Kotlin/Room mapping, proposed `/api/v1`
contracts, screen list and Kotlin/Compose/MVVM/Clean Architecture design are in
`ANDROID_MIGRATION_BLUEPRINT.md`.

The recommended boundary is:

```text
Compose UI → ViewModel → Use Case → Repository
             ↓                    ↓
          StateFlow       Retrofit + Room + WorkManager
                                  ↓
                    Django HTTPS JSON API
                                  ↓
                      Database + Prediction API
```

Django should remain the authority for identity, roles, validation, audit and
prediction persistence. The Android client should never connect directly to the
classifier or store password hashes.

## 7. Thesis Documentation Materials

`THESIS_DOCUMENTATION.md` contains:

- Mermaid system architecture diagram.
- Level-1 data-flow diagram.
- Image-upload sequence diagram.
- Chapter 4 technical narrative covering implementation, CV integration,
  agronomic estimation, testing, Android direction and limitations.

Thesis defense risks:

1. Confidence may be incorrectly presented as model accuracy.
2. The smoke-test image was classified as VMC 84-947 despite a filename
   suggesting VMC 84-524; only labeled independent evaluation can resolve correctness.
3. Weighted agronomic outputs require authoritative references and field validation.
4. Ambiguous units can undermine report interpretation.
5. The external classifier is a network dependency and uses HTTP.
6. Hardcoded dashboard metrics may be challenged as fabricated operational evidence.
7. Native Android remains a blueprint; current Android behavior is a WebView wrapper.

Likely panel questions include: What independent dataset validates the models?
How are LKG/TC and TC/HA defined? What happens offline? Why is confidence not
accuracy? Which component owns authentication? How are farmer images protected?
How is the database restored after failure?

## 8. Recommended Next Development Steps

1. Re-run `scripts/audit_local.py` and preserve the updated evidence from the four fixes.
2. Remove the remaining CSRF exemptions and unsafe password compatibility path.
3. Replace temporary password reset with verified, expiring recovery.
4. Validate units and prediction methodology with agriculture/domain advisers.
5. Add upload limits/private media and move the classifier behind HTTPS.
6. Add versioned Django JSON APIs with OpenAPI contract tests.
7. Build the farmer-only native Android vertical slice before admin screens.
8. Validate with independent labeled images and real harvest outcomes.
9. Rehearse backup restore, network failure and physical-device camera flows.
10. Only then configure a production WSGI/ASGI deployment and rerun `check --deploy`.

The safest thesis path is to freeze the verified Django demonstration after the
remaining security fixes, document its limitations honestly, and develop native
Android against stable versioned APIs in small, testable phases.
