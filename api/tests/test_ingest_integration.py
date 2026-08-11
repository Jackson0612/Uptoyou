#!/usr/bin/env python3
"""H14's named test, against a real PostgreSQL.

Run inside the stack:
    docker compose exec api python /srv/tests/test_ingest_integration.py

H14 names this test exactly, and names the weaker one it replaced:

    "Run a task twice and assert the table is identical" **proved nothing** — it passes
    under both the right key and the wrong one. The replacement: run the five o'clock
    task, run the six o'clock task, assert two rows exist for the seven o'clock hour and
    the first is unchanged; re-run the five o'clock task, assert there are still two;
    assert a pinned row still reads as it did when written.

That is the test below, translated to the key D42 actually settled on. Under hash-keying,
"the five o'clock task" is a fetch whose content is X and "the six o'clock task" is a fetch
whose content is Y, both carrying a reading for the *seven o'clock hour*. The property that
matters is unchanged: **two versions of one described hour both survive, and the earlier one
is not overwritten.** A round's snapshot (D15) pins a row, so an overwrite would silently
change what a past round is recorded as having read.

Observing a no-op by hand — which is what happened when item 10 first ran — is the weaker
claim this file exists to replace.

The test builds its own database and drops it, so it never touches the stack's data.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from upto.ingest.cwa import FORECAST_DATASET, ForecastRow, Publication  # noqa: E402
from upto.ingest.store import store_publication  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
TEST_DB = "upto_h14_check"

SEVEN_OCLOCK = datetime(2026, 8, 11, 19, 0, tzinfo=TAIPEI)


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


def publication(hash_value: str, temperature: str, detected_at: datetime) -> Publication:
    """One fetch, carrying a reading for the seven o'clock hour."""
    return Publication(
        dataset_id=FORECAST_DATASET,
        content_sha256=hash_value,
        detected_at=detected_at,
        payload_bytes=1024,
        forecast_rows=[
            ForecastRow(
                # D26 keys the forecast by geocode since revision 0003; 中山區 is 63000040.
                township_code="63000040",
                township="中山區",
                element="溫度",
                measure="Temperature",
                slot_start=SEVEN_OCLOCK,
                slot_end=SEVEN_OCLOCK + timedelta(hours=1),
                value=temperature,
            )
        ],
    )


async def scenario(test_url: str) -> None:
    engine = create_async_engine(test_url, poolclass=None)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    five_oclock = publication("a" * 64, "32", datetime(2026, 8, 11, 17, 5, tzinfo=TAIPEI))
    six_oclock = publication("b" * 64, "33", datetime(2026, 8, 11, 18, 5, tzinfo=TAIPEI))

    async with Session() as session:
        first = await store_publication(session, five_oclock)
    assert first.stored, "the five o'clock task must have written a publication"

    async with Session() as session:
        second = await store_publication(session, six_oclock)
    assert second.stored, "the six o'clock task published different content and must be stored"

    async def rows_for_seven():
        async with Session() as session:
            result = await session.execute(
                text(
                    "select p.content_sha256, r.value, p.detected_at "
                    "from forecast_reading r join forecast_publication p on p.id = r.publication_id "
                    "where r.slot_start = :slot order by p.detected_at"
                ),
                {"slot": SEVEN_OCLOCK},
            )
            return result.fetchall()

    rows = await rows_for_seven()
    assert len(rows) == 2, "expected two versions of the seven o'clock hour, got {}".format(len(rows))
    assert rows[0].value == "32", "the earlier reading was overwritten: {}".format(rows[0].value)
    assert rows[1].value == "33"

    # The pinned row: what a round's snapshot would have recorded.
    pinned = (rows[0].content_sha256, rows[0].value)

    # Re-run the five o'clock task. Same content, so nothing new — and, critically, the row
    # it wrote the first time must be untouched.
    async with Session() as session:
        rerun = await store_publication(session, five_oclock)
    assert not rerun.stored, "re-running the five o'clock task must be a silent no-op"
    assert rerun.rows_written == 0

    rows = await rows_for_seven()
    assert len(rows) == 2, "the re-run changed the row count to {}".format(len(rows))
    assert (rows[0].content_sha256, rows[0].value) == pinned, "the pinned row moved under a re-run"

    # And a re-run of the six o'clock task, for symmetry: the later version must not
    # displace the earlier one either.
    async with Session() as session:
        await store_publication(session, six_oclock)
    rows = await rows_for_seven()
    assert len(rows) == 2
    assert rows[0].value == "32" and rows[1].value == "33"

    await engine.dispose()
    print("H14: two versions of one described hour both survive; the earlier is unchanged under re-run")


async def with_temporary_database() -> int:
    admin_url, test_url = urls()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text('drop database if exists "{}"'.format(TEST_DB)))
        await connection.execute(text('create database "{}"'.format(TEST_DB)))
    await admin.dispose()

    try:
        environment = dict(os.environ, UPTO_DATABASE_URL=test_url)
        migrate = subprocess.run(
            ["alembic", "upgrade", "head"], cwd="/srv", env=environment, capture_output=True
        )
        if migrate.returncode != 0:
            print(migrate.stderr.decode("utf-8", "replace"), file=sys.stderr)
            return 2
        await scenario(test_url)
    finally:
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as connection:
            await connection.execute(text('drop database if exists "{}" with (force)'.format(TEST_DB)))
        await admin.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(with_temporary_database()))
