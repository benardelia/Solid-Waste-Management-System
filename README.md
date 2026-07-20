# 🗑️ Solid Waste Management System — Backend API

A production-ready Django & GraphQL backend for managing solid waste collection operations in Tanzania. Built to power the **SolidWaste** Flutter mobile application, supporting field workers, land officers, environment officers, and administrators.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [CI/CD Pipeline](#cicd-pipeline)

---

## Overview

The system manages waste collection across **Project Areas**, tracking:
- 🏠 **Households** and 🏢 **Institutes** registered in each area
- 🚛 **Collection records** logged by field workers via the mobile app
- 💰 **Monthly fee collection** tracking and performance reporting
- 👥 **Multi-role user management** (Admin, Worker, Land Officer, Environment Officer)

Live at: **https://solidwastemanagement.duckdns.org**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.x |
| API | GraphQL (`graphene-django`) + REST (`djangorestframework`) |
| Database | PostgreSQL 15 |
| Auth | Firebase Authentication (mobile) + JWT (REST) |
| Static Files | WhiteNoise |
| Container | Docker + Docker Compose |
| Web Server | Gunicorn (prod) + Nginx reverse proxy |
| CI/CD | GitHub Actions → SSH deploy to VPS |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                Flutter Mobile App               │
│     (Firebase Auth → Bearer token in header)   │
└───────────────┬───────────────┬─────────────────┘
                │ GraphQL       │ REST (Reports)
                ▼               ▼
┌─────────────────────────────────────────────────┐
│          Nginx Reverse Proxy (HTTPS)            │
│         solidwastemanagement.duckdns.org        │
└───────────────────────┬─────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│        Django + Gunicorn  (port 8003)           │
│  ┌───────────────┐   ┌─────────────────────┐   │
│  │  core app     │   │  wastemanager app   │   │
│  │  - User model │   │  - ProjectArea      │   │
│  │  - Firebase   │   │  - Household        │   │
│  │    auth       │   │  - Institute        │   │
│  │  - Auth       │   │  - CollectionRecord │   │
│  │    decorator  │   │  - GraphQL Schema   │   │
│  └───────────────┘   └─────────────────────┘   │
└───────────────────────┬─────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│            PostgreSQL 15 Database               │
└─────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- A Firebase project with a service account key

### 1. Clone the repository

```bash
git clone https://github.com/benardelia/Solid-Waste-Management-System.git
cd Solid-Waste-Management-System
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values (see [Environment Variables](#environment-variables) below).

### 3. Add Firebase credentials

Place your Firebase service account JSON file at:
```
secret_keys/firebase_service_account_keys.json
```

> You can download this from Firebase Console → Project Settings → Service Accounts → Generate new private key.

### 4. Start with Docker

```bash
docker compose up -d --build
```

This will:
- Start a **PostgreSQL 15** database container
- Build and start the **Django** web container
- Automatically run `migrate`
- Serve the app on **http://localhost:8003**

### 5. Create a superuser

```bash
docker compose exec web python manage.py createsuperuser
```

### 6. Access the services

| Service | URL |
|---|---|
| Django Admin | http://localhost:8003/admin/ |
| GraphQL Playground | http://localhost:8003/graphql/ |
| REST API | http://localhost:8003/api/ |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```env
# Django
SECRET_KEY="your-very-secret-key"
DEBUG=True

# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=wastemanagement
DB_USER=postgres
DB_PASSWORD=yourpassword

# Security
ALLOWED_HOSTS=*
DOMAIN_NAME=solidwastemanagement.duckdns.org
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Firebase
FIREBASE_CREDENTIALS=secret_keys/firebase_service_account_keys.json
```

> **⚠️ Never commit your `.env` or `secret_keys/` directory to version control.**

---

## API Reference

### Authentication

All API endpoints require a Firebase Bearer token in the `Authorization` header:

```
Authorization: Bearer <firebase_id_token>
```

The `JWTGraphQLView` middleware in `core/graphql/auth_decorator.py` verifies the token and attaches the user to the request context automatically.

---

### GraphQL Endpoint: `/graphql/`

#### Queries

```graphql
# Get all project areas
query { getAllAreas { id name monthlyFee } }

# Get paginated households (optionally filter by area)
query GetHouseholds($areaId: Int, $page: Int) {
  getAllHouseholds(areaId: $areaId, pagination: { page: $page, pageSize: 20 }) {
    items { id ownerName ward village lastCollectionStatus }
    pagination { totalPages hasNext }
  }
}

# Get collection records (filter by area, status, or worker)
query GetCollections($areaId: Int, $status: String) {
  getAllCollections(areaId: $areaId, status: $status) {
    items { id status amountCollected timestamp }
  }
}

# Get monthly revenue stats per area
query { getAreaMonthlyStats { areaId areaName expectedAmount collectedAmount } }
```

#### Mutations

```graphql
# Register a new household
mutation CreateHousehold($areaId: Int!, $ownerName: String!, ...) {
  createHousehold(areaId: $areaId, ownerName: $ownerName, ...) {
    success
    household { id ownerName }
  }
}

# Log a waste collection event
mutation LogCollection($areaId: Int!, $householdId: Int, $status: String!, $amountCollected: Float!) {
  logCollection(areaId: $areaId, householdId: $householdId, status: $status, amountCollected: $amountCollected) {
    success
    collection { id status timestamp }
  }
}

# Register an institute
mutation RegisterInstitute($ownersName: String!, $areaId: Int!, ...) {
  registerInstitute(ownersName: $ownersName, areaId: $areaId, ...) {
    success
  }
}
```

---

### REST Endpoints: `/api/`

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/api/areas/` | List / create project areas |
| GET/PUT/DELETE | `/api/areas/{id}/` | Retrieve / update / delete an area |
| GET/POST | `/api/households/` | List / create households |
| GET/POST | `/api/institutes/` | List / create institutes |
| GET/POST | `/api/collections/` | List / log collection records |
| GET | `/api/areas/{id}/stats/` | Area financial stats (supports `?start_date=` & `?end_date=`) |

---

## Project Structure

```
Solid-Waste-Management-System/
├── SolidWasteManagementSystem/     # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── schema.py                   # Root GraphQL schema
│   └── wsgi.py
│
├── core/                           # Core / shared app
│   ├── models.py                   # AuditableModel base, custom User
│   ├── firebase_auth.py            # Firebase token verification
│   ├── middleware.py               # CurrentUserMiddleware (for AuditableModel)
│   └── graphql/
│       ├── auth_decorator.py       # @authenticate_mutation / @authenticate_graphql_api
│       └── pagination.py
│
├── wastemanager/                   # Main business logic app
│   ├── models.py                   # ProjectArea, Household, Institute, CollectionRecord
│   ├── admin.py                    # Django admin configuration
│   ├── views.py                    # REST viewsets + AreaStatsView
│   ├── serializers.py
│   └── graphql/
│       ├── queries/area.py         # All GraphQL queries
│       ├── mutations/area.py       # All GraphQL mutations
│       └── types/area.py           # GraphQL types
│
├── docker-compose.yml              # Local development
├── docker-compose.prod.yml         # Production overrides (Gunicorn, no exposed ports)
├── Dockerfile
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── deploy.yml              # Auto-deploy on push to main
```

---

## Deployment

### Production Stack

The production environment uses:
- **Docker Compose** with the prod override file
- **Gunicorn** as the WSGI server
- **Nginx** as a reverse proxy (external `global-proxy-network`)
- **Let's Encrypt** for automatic HTTPS via `LETSENCRYPT_HOST`

### Deploy Manually

```bash
# On the VPS, in the project directory:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec -T web python manage.py migrate
docker compose exec -T web python manage.py collectstatic --noinput
```

### Database Issues

If migrations fail with `database "wastemanagement" does not exist`:

```bash
docker compose exec db createdb -U postgres wastemanagement
docker compose exec web python manage.py migrate
```

---

## CI/CD Pipeline

Every push to the `main` branch triggers the GitHub Actions workflow (`.github/workflows/deploy.yml`), which:

1. SSHes into the VPS using the `VPS_SSH_KEY` secret
2. Pulls the latest code with `git pull origin main`
3. Rebuilds Docker images with `docker compose ... up -d --build`
4. Runs `python manage.py migrate` automatically

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `VPS_HOST` | IP address or hostname of your VPS |
| `VPS_USERNAME` | SSH username (e.g. `root`) |
| `VPS_SSH_KEY` | Private SSH key for authentication |

---

## User Roles

| Role | Permissions |
|---|---|
| `admin` | Full access — all areas, all data, user management |
| `land_officer` | Register and manage households and institutes |
| `env_officer` | View collection records and reports |
| `worker` | Log collections for their assigned area only |

---

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'feat: add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request against `main`

---

## License

This project is private and proprietary. All rights reserved.
