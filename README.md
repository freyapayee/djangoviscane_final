# VISCANE Setup

This codebase now runs on Django.

## Start locally

```bash
cp .env.example .env.local
.env/bin/pip install -r requirements.txt
.env/bin/python manage.py runserver 0.0.0.0:5000
```

## Docker

```bash
docker compose up --build
```

## Notes

- Keep `.env.local` private
- The Django project reuses the existing templates and static assets in this folder
- PostgreSQL is supported via `DATABASE_URL`, with SQLite fallback when it is omitted
