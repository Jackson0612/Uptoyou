"""The three name-fixing sources on a schedule — D77 brands, D78 storefront signs, D81 registry
status. One file, three DAGs, because they are the same shape three times.

Ruled 2026-08-14: these sources ran by hand while they were being built; from here they run
themselves. Each is thin the way `place_reference_ingest.py` is thin — fetch, hash and parse
live in `upto.ingest`, this file supplies only *when* and *with which database*.

**Daily against slow-moving files, and it is D34's aliasing argument again.** The 食材登錄 and
衛生評核 CSVs have no publication rhythm anyone has observed; the 商業登記 roster is monthly. A
schedule matched to a guessed rhythm leaves the phase to luck; a daily poll bounds staleness at
a day and costs a few MB a fetch. The no-change days are not waste: each writes a `no_change`
row to `ingest_run`, and a ledger with a daily heartbeat is what makes a silently broken source
distinguishable from a quiet one — the absence-vs-absence problem `ingest_run` exists to solve.

**No exit 2 here.** These are bare CSVs with no archive stamp, so there is no second version
signal to disagree with the content hash (the item-11 DAG's exit-2 lore does not apply). Exit 0
is stored-or-no-change, exit 1 is the source failing.

**`--file` never appears here** — item 11's rule, restated because this is the file where it
would be tempting: a local file in a DAG turns the operator's hand-run mistakes into pipeline
history.

**Schedules are staggered after the 03:00 FDA fetch** — quiet hours, one download at a time,
no alignment attempted or claimed.

Like every DAG in this repository: no backfill (the endpoints serve only the current file), so
`catchup=False`; a new DAG arrives **paused** and a triggered run sits queued forever until
`airflow dags unpause <dag_id>` — the hazard is in CLAUDE.md and it has cost hours once already.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta

from airflow.hooks.base import BaseHook
from airflow.sdk import dag, task

POSTGRES_CONNECTION = "upto_postgres"

# (dag_id suffix, module, source label as printed by the runner, cron, tags)
SOURCES = (
    (
        "brand",
        "upto.ingest.run_brands",
        "foodtracer-brands",
        "20 3 * * *",
        ["ingest", "d77", "brands", "reference"],
    ),
    (
        "storefront",
        "upto.ingest.run_storefronts",
        "gradelist-storefronts",
        "40 3 * * *",
        ["ingest", "d78", "storefronts", "reference"],
    ),
    (
        "business_status",
        "upto.ingest.run_business_status",
        "gcis-status",
        "0 4 * * *",
        ["ingest", "d81", "registry-status", "reference"],
    ),
)


def _database_url() -> str:
    """Build the async URL from the Connection, at run time and never before."""
    connection = BaseHook.get_connection(POSTGRES_CONNECTION)
    return "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
        connection.login,
        connection.password,
        connection.host,
        connection.port or 5432,
        connection.schema,
    )


def _make(name: str, module: str, source: str, cron: str, dag_tags: list[str]):
    @dag(
        dag_id=f"upto_{name}_ingest",
        description=f"{source} — daily, deduplicated by content hash",
        schedule=cron,
        start_date=datetime(2026, 8, 14),
        catchup=False,
        max_active_runs=1,
        default_args={
            "retries": 2,
            "retry_delay": timedelta(minutes=10),
            "depends_on_past": False,
        },
        tags=dag_tags,
    )
    def _ingest_dag():
        @task(task_id=name)
        def run() -> str:
            """One fetch; most days store nothing, and that no-op is recorded by design."""
            interpreter = os.environ.get("UPTO_PYTHON", "/opt/upto/venv/bin/python")
            src = os.environ.get("UPTO_SRC", "/opt/upto/src")

            environment = dict(os.environ)
            environment["PYTHONPATH"] = src
            environment["UPTO_DATABASE_URL"] = _database_url()
            # A scheduled run and a hand-triggered one are different answers to "why does
            # this row exist" — absent, the run records itself as `cli`, a wrong fact.
            environment["UPTO_INVOKED_BY"] = "airflow"

            finished = subprocess.run(
                [interpreter, "-m", module],
                env=environment,
                capture_output=True,
                text=True,
            )
            if finished.stdout:
                print(finished.stdout.strip())
            # stderr's tail carries the diagnosis; truncating from the front cost an hour
            # on the weather DAG once.
            stderr = (finished.stderr or "").strip()
            if stderr and finished.returncode != 0:
                print(stderr)
            if finished.returncode != 0:
                raise RuntimeError(
                    "{} ingest failed: {}".format(source, stderr[-500:] or "no stderr at all")
                )
            return finished.stdout.strip()

        run()

    _ingest_dag()


for _name, _module, _source, _cron, _tags in SOURCES:
    _make(_name, _module, _source, _cron, _tags)
