# VISCANE Setup

This codebase now runs on Django.

## Start locally

Create a project virtual environment with Python 3. The dependencies installed
successfully with Python 3.14 here, using prebuilt wheels for the scientific
packages. Docker uses Python 3.11.

```bash
cp .env.example .env.local
python3 -m venv .venv-local
.venv-local/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv-local/bin/python manage.py migrate
.venv-local/bin/python manage.py runserver 0.0.0.0:5000
```

The binary-only install makes pip stop with a clear error instead of spending a
long time compiling scientific packages when a prebuilt wheel is unavailable.

For Windows, follow [WINDOWS_SETUP.md](WINDOWS_SETUP.md). Local databases,
private uploads and TLS keys are excluded from Git; run migrations on a new
checkout to create its database. Android client source and build instructions
are in the [Flask/Android repository](https://github.com/freyapayee/falshviscane).

## Docker

```bash
docker compose up --build
```

## Prediction Service

The Django app expects the separate Sugarcane Variety Classifier API to be running
before you upload a scan.

If you are running the predictor locally, start it with:

```bash
uvicorn sugarcane_variety.api:app --host 0.0.0.0 --port 8000
```

Then set `SCAN_PREDICT_ENDPOINT` to the API's `/predict` route.
If Django is running inside Docker on macOS, use `http://host.docker.internal:8000/predict`.

## Hiligaynon mode

Choose **Hiligaynon** from the language selector on farmer or admin pages. Django
stores the selection in a language cookie. The interface catalog covers the main
farmer workflows, agronomic inputs, recommendations, and common admin controls.
Some live content and uncommon labels may remain in English; review the wording
with local farmers before a full release.

For DeepSeek translations of recommendation text, install `requirements.txt` and
set `DEEPSEEK_API_KEY` in `.env.local` or your deployment environment. The API key
is read by Django and must never be added to templates or browser JavaScript.
Without a key, standard recommendation titles, tags, and agronomic guides still
have local Hiligaynon text. DeepSeek can translate remaining recommendation
explanations. The original English text is available under each translated
recommendation for checking its meaning.

The scan screen says **Accuracy** as requested, but its per-image percentage is
the model's confidence score. Measured model accuracy requires labeled test
images and is shown separately in the superadmin dashboard.

The locale catalog in `locale/hil/LC_MESSAGES` enables Django to recognize
Hiligaynon. If adding Django gettext translations later, update `django.po` and
compile it to `django.mo` with `python manage.py compilemessages` (GNU gettext
utilities required).

## Notes

- Keep `.env.local` private
- The Django project reuses the existing templates and static assets in this folder
- PostgreSQL is supported via `DATABASE_URL`, with SQLite fallback when it is omitted
- `SCAN_PREDICT_ENDPOINT` must point to a working image-prediction API that returns JSON from the `/predict` route
