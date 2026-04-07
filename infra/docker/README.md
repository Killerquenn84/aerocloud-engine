# AeroCloud Docker Compose — Dev Stack

## Quickstart

```bash
# From the infra/docker/ directory
docker compose up -d postgres redis
pg_isready -h localhost -U aerocloud
redis-cli -h localhost ping
```

## Services

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| postgres | `postgres:16-alpine` | Database with pgvector | 5432 |
| redis | `redis:7-alpine` | Celery broker + cache | 6379 |
| api | `aerocloud-api:dev` (built) | FastAPI HTTP surface (Phase 12) | 8000 |
| worker | `aerocloud-worker:dev` (built) | Celery GPU worker (Phase 12) | — |

## Build

Run from repo root (build context must include the full repo):

```bash
docker compose -f infra/docker/docker-compose.yml build api
docker compose -f infra/docker/docker-compose.yml build worker
```

## Credentials (dev only — never in prod)

- Postgres: `aerocloud` / `devpassword` / database `aerocloud`
- Redis: no auth (bound to localhost via docker-compose)

## Teardown

```bash
docker compose -f infra/docker/docker-compose.yml down -v
```

The `-v` flag removes the `postgres-data` volume.
