# Up to you

A self-hosted app for a small group deciding where to eat. Open a round, propose places, roll two
dice — and read, on a reveal panel, exactly how the odds got that way. Every factor that moved a
place's weight is stored as its own row, pinned to the reading it was computed from, so the result
is an auditable decision rather than a number that appeared.

Behind it sits the part this repository is really about: six scheduled sources, content-addressed so
an unchanged file costs nothing, a run ledger where a no-change day is a recorded heartbeat, and
lineage from any reading back to the run that wrote it.

## Stack

- **API** — Python, FastAPI, SQLAlchemy 2.0, async end to end, 17 hand-written Alembic migrations
- **Database** — PostgreSQL 17; Airflow's metadata is a second database in the same instance
- **Orchestrator** — Apache Airflow 3, LocalExecutor, same compose stack
- **Model** — Ollama serving `qwen2.5:3b-instruct-q4_K_M`, behind a compose profile
- **Front end** — Vue 3 global build; no build step, no node, no CDN. nginx serves the files.

## The pipeline

| DAG | Schedule (UTC) | Taipei | Source |
|---|---|---|---|
| `upto_weather_ingest` | hourly | hourly | CWA township forecast `F-D0047-061` + station observations `O-A0001-001` |
| `upto_place_reference_ingest` | `0 19 * * *` | 03:00 next day | 食藥署 食品業者登錄 — the restaurant reference list |
| `upto_brand_ingest` | `20 19 * * *` | 03:20 next day | 臺北市食材登錄平台 — company ↔ brand pairs |
| `upto_storefront_ingest` | `40 19 * * *` | 03:40 next day | 臺北市餐飲衛生分級評核 — the sign an inspector saw |
| `upto_business_status_ingest` | `0 20 * * *` | 04:00 next day | 商業登記-餐館業 — which registrations are dead |
| `upto_business_tax_ingest` | `20 20 * * *` | 04:20 next day | 財政部 全國營業(稅籍)登記 — tax name + industry code |

**The crons are UTC, and the quiet hours they aim at are Taipei's.** Airflow's
`core.default_timezone` is `utc` here, so the two columns are the same instant read on two
clocks — the daily sources fetch between 03:00 and 04:20 Taipei, one download at a time.

**A publication is identified by the hash of its bytes, not by a timestamp.** A stamp can move
while the data stands still, and stand still while the data moves. The content hash is the key;
the file's own stamp is kept beside it as a label, and where both exist they are compared every
run — a disagreement exits 2 and fails the task deliberately.

**The cheap half gates the expensive half.** The reference ingest fetches a 17 MB zip, hashes the
compressed bytes, and claims the publication with `insert … on conflict do nothing returning id`
— the *database* decides whether the content is new. Only then does anything decompress the
99 MB CSV inside (827,784 rows, of which the **36,499** Taipei restaurant rows are kept). The
file is monthly and the poll daily, so ~29 runs a month find nothing and must be silent successes.

**A run that wrote nothing is still a run.** Every attempt writes an `ingest_run` row, and
`no_change` and `failed` are different recorded outcomes — inferred from an absence they are
indistinguishable, which is how a broken source looks healthy for a week.

**Lineage is served to a model too.** Any reading traces to its publication, its content hash and
the run that wrote it, over MCP on stdio:

```sh
docker compose exec -T api python -m upto.lineage.mcp_server
```

Five tools answer: `run_history`, `run_detail`, `publication_detail`, `forecast_reading_source`,
`observation_reading_source`. A sixth, `explain_place_loss`, is listed **only in order to
refuse** — the honest trail runs into private per-member vetoes, and a tool that merely lacks a
feature today grows it the first time somebody finds it useful. A test asserts the refusal.

### The sixth source, landed

The tax registry is the widest file here: a 66 MB zip holding one ~320 MB CSV of **1,711,012 rows
— every registered business in the country.** Only rows whose 統編 already appears in the latest
reference publication are stored: **14,521 kept against 19,203 reference numbers, in about 15
seconds.** The other ~1.69M are never written — a storage decision, not an optimisation: a tax row
for a hardware store two hundred kilometres away answers nothing this app asks.

It publishes what nothing else did — the 營業人名稱 the tax office holds, and the **行業代號 the
business registered itself under**, an official category the shop chose rather than one a model
guessed. The four code/name pairs are stored positionally: the first is the primary trade, and
compacting the empty tail would silently promote a secondary one. Stored now, read by nothing yet.
One warning sits in the schema: `business_tax_row.address` is the **registered** address, not the
storefront — 6.2% of matched rows sit outside 臺北市 — and nothing may join on it.

## Names and categories

**A registered name is a legal entity, not a shop.** The reference list knows
安心食品服務股份有限公司; the people deciding where to eat know 摩斯漢堡. So a display name resolves at
read time down a ladder — **storefront sign → brand → registered name.** The sign wins: an inspector
recorded it against the same registry number, so that join needs no name matching at all (1,686 rows,
1,379 joining the current publication). The brand applies only where a company maps to exactly one
(188 of 266 join; a multi-brand company keeps its registered name, because nothing in either source
says which brand this site is). A 統編 the registry records as dead — and never alive — drops out of
the search typeahead, names elsewhere untouched.

**Categories are ten values, closed:** 麵食 · 飯食 · 小吃 · 火鍋 · 燒烤 · 日式 · 西式 · 早餐 ·
咖啡飲料 · 其他. An answer outside the list is **refused, never repaired** — coercing 拉麵 into 麵食
turns a wrong answer into a plausible one, and deletes the only step in the process that can fail.

Classification runs as a batch against a locally deployed quantized 3B model, off unless a backfill
is running (it peaks around 2.1 GB; the deployment target has 4). The model is asked the best name
the project holds — the same ladder — and every decided row records **the prompt version, the model
name, and the exact string that was asked.** A legal-entity verdict is written as a decided absence:
provenance present, category null, so re-runs never re-ask it. Batches commit as they go, so an
interrupted seven-hour pass resumes where it stopped.

**Set up to be measured, not asserted.** `evaluate/testset_v1.json` is a frozen, hand-labeled set of
**200 names**, drawn deterministically — fixed seed, stratified by which layer of the ladder supplied
the name, floor of 30 per layer so the small sign and brand strata stay scorable. Frozen so scores
stay comparable across prompt versions, which carry a version string that changes with the text.

## Privacy

**Authorship dies at the close, in the database.** Closing a round fires a trigger that nulls
`proposal.member_id` for that round, in the transaction that makes the result durable. A trigger
rather than application code, because a manual close over SQL, a fix-up script or a second code path
would each leave authorship behind and none would error. Nothing on the live stream carries a member.

## Quick start

```sh
cp .env.example .env      # names only — the comments state the shape of every value
docker compose up -d --wait
curl -s localhost:8080/health   # {"status":"ok","database":"reachable"}
```

- **`localhost:8080`** — the app (`UPTO_HTTP_PORT`), the only port the product publishes; the API
  and the database are reachable only over the compose network.
- **`localhost:8081`** — the Airflow UI (`AIRFLOW_HTTP_PORT`), user `admin`.
- The weather ingest needs a free CWA Open Data key (opendata.cwa.gov.tw), read once at init into a
  Fernet-encrypted Airflow Connection — never from the environment, never into XCom or a rendered
  template field. The five open-data files need no credential. New DAGs arrive **paused**
  (`airflow dags unpause <dag_id>`).

Run an ingest by hand — `0` stored or no change, `1` the source failed, `2` the version signals
disagree — or bring the model up for a backfill:

```sh
docker compose exec api python -m upto.ingest.run_places
docker compose exec api python -m upto.ingest.run_business_tax

docker compose --profile model up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b-instruct-q4_K_M
docker compose exec api python -m upto.classify.run 63000010   # exit 3 = model absent, nothing written
```

## Tests

32 test files. Fetch, hash and parse are unit-tested with no network and no database, which is what
keeps the DAGs thin — they supply only *when* and *with which database*:

```sh
python3 api/tests/test_cwa_ingest.py    # and test_fda_ingest, test_fia_ingest, test_dice_table,
python3 api/tests/test_weight_fold.py   # test_classify, test_web_surface, test_evaluate_draw …
```

Integration tests build and drop their own database inside the stack:

```sh
docker compose exec api python /srv/tests/test_place_ingest_integration.py
docker compose exec api python /srv/tests/test_business_tax_integration.py
```

## Scope

Taipei only — twelve townships, one city's open data, addresses normalised at the ingest boundary
because the same government file spells the city two ways. Sized for one small group: one API
worker, live room state in memory, five friends rather than five thousand. A portfolio project,
developed in a private repository and extracted here after every merge, so the commit messages
carry the reasoning behind each change.
