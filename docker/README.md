# docker

| Folder | What it is |
|---|---|
| `backend/Dockerfile` | The API image: Python 3.12 + uv, bakes in the embedding model, gunicorn on :8080, non-root. Works on ARM64 and x86_64 |
| `postgres/Dockerfile` | Postgres 16 with PostGIS and pgvector, used by `docker-compose.yml` and CI |

## Run
```
make up                  # start Postgres and Redis locally
make build-api           # build the API image
```

## Test
`backend/tests/unit/test_deploy_image.py` checks the backend image rules. CI builds the postgres image.
