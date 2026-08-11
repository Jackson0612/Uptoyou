"""MVP item 11 on a schedule — the 食藥署 reference ingest, daily.

Thin for the same reason `weather_ingest.py` is thin: fetching, hashing and parsing live in
`upto.ingest`, unit-tested with no network and no database, and this file supplies only *where
the credentials come from* and *when it runs*.

**Daily against a monthly file, and that is D34's aliasing argument rather than generosity.** A
monthly poll of a monthly file leaves the phase to luck and can be two months stale; a daily one
is bounded at a day. The cost is twenty-nine fetches a month that publish nothing — 17 MB each,
about two seconds — and those runs must be **silent successes**. They do not even decompress the
CSV: the content hash is read from the compressed bytes, so an unchanged day never touches the
99 MB inside.

**One task, not two.** Item 10 splits observation from forecast because a forecast failure must
not stop the hourly observation. Here there is one file and one publication, so a second task
would only be a second thing to explain.

**Credentials: only the database one exists.** D33 counts the sources and this is the one needing
no key — the file is an open download — so the only Connection read here is `upto_postgres`, and
it is handed to the subprocess as environment for the reason the weather DAG states: a task
argument lands in XCom and a templated env lands in the UI's rendered fields, and both of those
are the metadata database.

**Exit code 2 means the two version signals disagree** — the archive stamp says one thing about
whether anything changed and the content hash says another (D34, D35). The task is failed
deliberately in that case, and the verdict printed above the failure says whether anything was
stored: content can move while the stamp stands still, and the stamp can move while the content
stands still. Whatever the run decided to write is already written when the task turns red, so red
here means "come and read the log", not "the data is missing"; a printed warning on a green task is
a fact filed where nobody looks.

**What this DAG cannot honestly do: backfill.** The endpoint serves the current file and has no
history, so triggering a past interval fetches today's bytes and stores them under today's hash —
the same limitation `weather_ingest.py` records, from a different publisher. `catchup=False` for
that reason.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta

from airflow.hooks.base import BaseHook
from airflow.sdk import dag, task

POSTGRES_CONNECTION = "upto_postgres"

# Stored on the publication row and printed in every verdict line. Kept in step with
# `upto.ingest.fda.SOURCE` by hand, because this file must not import the ingest package —
# Airflow parses DAGs in its own interpreter, and the ingest lives in a separate venv.
SOURCE = "fda-97"

DISAGREEMENT = 2


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


@dag(
    dag_id="upto_place_reference_ingest",
    description="Item 11 — 食藥署 食品業者登錄 餐飲場所, daily, deduplicated by content hash",
    # 03:00 Taipei. Away from the hourly weather ingest's own minute, and at an hour when a
    # 17 MB download competes with nothing. The publisher has never been observed to publish at
    # a particular time of day, so this is a quiet hour rather than an aligned one — and D34's
    # whole point is that no alignment is being attempted.
    schedule="0 3 * * *",
    start_date=datetime(2026, 8, 11),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10), "depends_on_past": False},
    tags=["ingest", "item-11", "fda", "reference"],
)
def upto_place_reference_ingest():
    @task(task_id="reference_places")
    def reference_places() -> str:
        """One fetch. About twenty-nine of thirty runs a month store nothing, by design."""
        interpreter = os.environ.get("UPTO_PYTHON", "/opt/upto/venv/bin/python")
        source = os.environ.get("UPTO_SRC", "/opt/upto/src")

        environment = dict(os.environ)
        environment["PYTHONPATH"] = source
        environment["UPTO_DATABASE_URL"] = _database_url()

        finished = subprocess.run(
            [interpreter, "-m", "upto.ingest.run_places"],
            env=environment,
            capture_output=True,
            text=True,
        )
        # stdout carries the verdict — "stored…", "no change…", and the unresolved-township
        # report. It is printed whatever the exit code, because on a disagreement it is the
        # half that says what was written.
        if finished.stdout:
            print(finished.stdout.strip())
        if finished.returncode == DISAGREEMENT:
            raise RuntimeError(
                "{}: the archive stamp and the content hash disagree — the verdict above says "
                "what was written: {}".format(SOURCE, (finished.stderr or "").strip()[:500])
            )
        if finished.returncode != 0:
            raise RuntimeError(
                "{} ingest failed: {}".format(SOURCE, (finished.stderr or "").strip()[:500])
            )
        return finished.stdout.strip()

    reference_places()


upto_place_reference_ingest()
