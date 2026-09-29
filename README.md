# GreenHill EID Backend

Django REST Framework and PostgreSQL foundation for the GreenHill Enterprise Incident and Service Management platform. The browser application is in the separate Frontend repository.

The SRS describes the product requirements but leaves implementation technologies open. The project team selected React + Vite + TypeScript for the frontend and Django REST Framework + PostgreSQL for the backend. This repository uses Django 6, Python 3.13, PostgreSQL 17, pytest, and Ruff.

## Current scope

This is a service foundation, not a finished product. It provides:

- Django project settings driven by environment variables.
- PostgreSQL in the local Docker Compose setup, with SQLite as the simple no-PostgreSQL fallback for local checks.
- A public GET /api/health/ endpoint for a basic process-level smoke check.
- A default authenticated permission policy for future API views; the health endpoint explicitly opts into public access.
- CORS restricted to the two local Vite origins by default.
- pytest, Ruff, Django system checks, migration checks, and a GitHub Actions workflow for pull requests to Dev.

No business models, roles, example records, or analytics have been invented. The SRS identity provider, detailed RBAC matrix, and product API contracts remain decisions for implementation planning. Keep real credentials and personal or student information out of test fixtures and source control.

## Requirements

- Python 3.13.
- Docker Desktop with Docker Compose v2 for the recommended local workflow.
- PostgreSQL 17 if running the application without Docker.

## Start with Docker

1. Copy .env.example to .env. The included values are for local development only.
2. From this repository directory, start the API and database:

       docker compose up --build

3. Open http://localhost:8000/api/health/.

The API container applies Django migrations on startup and then runs Django's development server. Stop the services with Ctrl+C, then run docker compose down. The named PostgreSQL volume preserves local database contents when containers stop. Do not use the development server as a production server.

## Start without Docker

Use a Python 3.13 virtual environment, install requirements.txt, and set the database environment variables to reach your local PostgreSQL instance. Set POSTGRES_HOST=localhost and POSTGRES_PORT=5432 when using the database published by the Compose file. Then run:

    python manage.py migrate
    python manage.py runserver

Open http://localhost:8000/api/health/. If POSTGRES_HOST is unset, Django uses SQLite for lightweight local checks.

## Commands

| Command | Purpose |
| --- | --- |
| python manage.py runserver | Start Django's local development server. |
| python manage.py check | Run Django project configuration checks. |
| python manage.py migrate | Apply committed migrations to the selected database. |
| pytest | Run the API test suite. |
| ruff check . | Lint Python files and check import ordering. |

## How tests work

Tests use pytest, pytest-django, and Django REST Framework's APIClient. The starter integration test makes an unauthenticated HTTP request to GET /api/health/ and checks the HTTP status and JSON response. This verifies URL routing, the view, and the public health-check permission in one small test.

The current test suite does not cover product workflows, database models, role-based access rules, external identity services, load behavior, or production deployment. Add tests with each feature: unit tests for isolated business rules, API tests for request/response and permission behavior, and database tests for constraints and migrations. Use anonymized synthetic data only.

The GitHub Actions workflow starts a disposable PostgreSQL service, installs the requirements, runs Ruff, Django checks, migration drift checks, and pytest on pushes to Dev and pull requests targeting Dev.

## Configuration and secrets

The Compose workflow reads .env. Use .env.example as a template and replace the development secret before any deployment. The example database password and Django secret are intentionally local-only values. Never commit .env, production secrets, or database dumps.

DJANGO_DEBUG should be disabled outside local development. Set DJANGO_ALLOWED_HOSTS to the exact hostnames used by the chosen environment. CORS_ALLOWED_ORIGINS is a comma-separated list; only add trusted frontend origins. Credentialed cross-origin requests are disabled by default.

## API foundation

The health route is GET /api/health/ and returns a small status response. It confirms that the application process can serve a request; it is not a full database or dependency readiness check.

Future endpoints belong in a dedicated Django app as their SRS workflows are implemented. Keep authorization explicit for every resource and test both allowed and denied access. The global REST Framework default is IsAuthenticated; public endpoints must opt in deliberately.

## Branch and review workflow

- Create work from Dev using a short-lived branch such as feature/<name> or fix/<name>.
- Open a pull request into Dev and summarize the API, migrations, permission impact, and testing performed.
- The team reviews and merges approved work into Dev.
- The team lead promotes Dev to main through a separate pull request after the release checks and review.

The repositories are currently on the GitHub Free plan. GitHub displayed the existing private-repository branch rules as not enforced on that plan, so the PR flow is a team convention until the organization confirms server-side enforcement is available. Do not treat local Git hooks as a security boundary.

## Deployment

No deployment workflow is configured. The initial hosting provider is still to be selected, and the project may later move to DigitalOcean. Before deployment, select a production WSGI/ASGI server, configure HTTPS and secure Django settings, provision managed PostgreSQL and backups, define secret handling, and document deployment approvals and rollback.

## Repository layout

    .github/workflows/ci.yml   Pull-request and Dev validation
    config/                    Django settings and ASGI/WSGI entry points
    core/                      Health endpoint and starter API test
    manage.py                  Django management entry point
    requirements.txt           Runtime and foundation validation dependencies

