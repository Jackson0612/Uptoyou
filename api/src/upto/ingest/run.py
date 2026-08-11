"""Run item 10's ingest once. The entry point a scheduler calls, and a human can call.

Airflow is not in the stack yet — it arrives with the DAG that replaces this module's
`main`. Until then this is how the ingest runs, and the split is deliberate: the fetch and
the write know nothing about who invoked them, so the DAG will call the same two functions
rather than a rewritten copy.

The key is read here and nowhere deeper. D33 rules it an Airflow Connection; this reads an
environment variable, which is the interim arrangement and the only place that changes when
the DAG lands.
"""

from __future__ import annotations

import asyncio
import os
import sys

from ..db import Session
from .cwa import FORECAST_DATASET, OBSERVATION_DATASET, CwaUnavailable, fetch_publication
from .store import store_publication

KEY_VAR = "UPTO_CWA_API_KEY"


def api_key() -> str:
    key = os.environ.get(KEY_VAR, "").strip()
    if not key:
        raise RuntimeError(
            "{} is not set. D33 rules this an Airflow Connection once the DAG exists; "
            "until then it is an environment variable, and the key itself lives at "
            "~/.cwa_api_key outside every repository.".format(KEY_VAR)
        )
    return key


async def ingest_once(datasets=(FORECAST_DATASET, OBSERVATION_DATASET)) -> int:
    key = api_key()
    failures = 0
    for dataset_id in datasets:
        try:
            publication = fetch_publication(dataset_id, key)
        except CwaUnavailable as failure:
            # A source that did not answer is a failure. A source that answered the same
            # thing as last time is not — that distinction is the whole of D42.
            print("{}: FAILED — {}".format(dataset_id, failure), file=sys.stderr)
            failures += 1
            continue
        async with Session() as session:
            result = await store_publication(session, publication)
        print(result.line())
    return 1 if failures else 0


def main() -> int:
    return asyncio.run(ingest_once())


if __name__ == "__main__":
    sys.exit(main())
