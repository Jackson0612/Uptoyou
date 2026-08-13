# Up to you

A self-hosted app for a small circle of friends deciding where to eat: open a round, propose
places, roll the dice, and read on a reveal panel exactly how the result came to be. Behind it
sits a scheduled data pipeline with per-reading lineage.

**Status: early, and public on purpose.** The pipeline is real and running; the product surface
is under construction. This repository is extracted per merge from a private working repository,
so commit messages carry the reasoning behind each change. This README is deliberately minimal
for now and grows with the code.

## Stack

- **API** — Python, FastAPI, SQLAlchemy, hand-written migrations
- **Front end** — Vue 3 global build, no build step, no node; static files served by nginx
- **Database** — PostgreSQL (one instance; a second database holds Airflow's metadata)
- **Orchestrator** — Apache Airflow, LocalExecutor, same compose stack
- **Everything** comes up with one `docker compose up`

## What runs today

- **Weather ingest** — Taiwan CWA township forecasts and station observations, fetched hourly,
  deduplicated by content hash, so a no-change run writes nothing and says so.
- **Place reference ingest** — the FDA restaurant registry, fetched daily against a monthly
  publication, keyed the same way.
- **A run ledger** — every ingest run is recorded, including the runs that wrote nothing;
  `no change` and `failed` are different recorded outcomes.
- **A lineage tool over MCP** — any stored reading traces to its publication, its content hash,
  and the run that wrote it: `docker compose exec -T api python -m upto.lineage.mcp_server`
- **A first read path** — `GET /api/weather` answers with the observation for the hour, else the
  forecast for that same hour, and always names the publication it used.

## Quick start

```sh
cp .env.example .env      # fill it in — the comments state the shape of every value
docker compose up -d --wait
curl -s localhost:8080/health   # {"status":"ok","database":"reachable"}
```

- Front end: `localhost:8080` · Airflow UI: `localhost:8081`
- The weather ingest needs a free CWA Open Data API key (opendata.cwa.gov.tw). It is read once
  at init into an encrypted Airflow Connection; tasks never read it from the environment.

## Tests

No network and no database needed:

```sh
python3 api/tests/test_cwa_ingest.py
python3 api/tests/test_fda_ingest.py
python3 api/tests/test_web_surface.py
python3 api/tests/test_lineage_mcp.py
```

Integration tests build and drop their own database inside the stack:

```sh
docker compose exec api python /srv/tests/test_ingest_integration.py
docker compose exec api python /srv/tests/test_place_ingest_integration.py
docker compose exec api python /srv/tests/test_identity_integration.py
```
