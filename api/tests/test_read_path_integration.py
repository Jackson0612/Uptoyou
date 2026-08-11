#!/usr/bin/env python3
"""Ticket 07's read path, against a real PostgreSQL.

Run inside the stack:
    docker compose exec api python /srv/tests/test_read_path_integration.py

The rows are planted rather than fetched, because the cases that matter are ones the live
data will not reliably present: an hour whose observation has not landed yet, an hour with
neither record, and two versions of one hour. The test builds its own database and drops it.

**The case the ticket names is the second one.** Inside the roughly ten-minute window before
an observation lands, the call must return the *forecast for that same hour* — never the
previous hour's observation. That is H15: a reading older than the hour it claims to describe
must never be returned silently.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from upto.read.weather import ForecastJoinBroken, TownshipUnknown, reading_for  # noqa: E402
from upto.seed import township_station as seed  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
TEST_DB = "upto_readpath_check"

SEVEN = datetime(2026, 8, 11, 19, 0, tzinfo=TAIPEI)
SIX = SEVEN - timedelta(hours=1)

SHILIN = "63000110"      # 士林區 → 社子 C0A980, resolved by lowest altitude
STATION = "C0A980"


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


async def plant_observation(session, hour, temperature, detected_at, sha):
    result = await session.execute(
        text(
            "insert into observation_publication (dataset_id, content_sha256, detected_at, payload_bytes) "
            "values ('O-A0001-001', :sha, :detected, 100) returning id"
        ),
        {"sha": sha, "detected": detected_at},
    )
    publication = result.scalar()
    for element, value in (("AirTemperature", temperature), ("Weather", "陰")):
        await session.execute(
            text(
                "insert into observation_reading (publication_id, station_id, station_name, county, "
                "town, town_code, observed_at, element, value) values (:p, :s, '社子', '臺北市', "
                "'士林區', :code, :hour, :element, :value)"
            ),
            {"p": publication, "s": STATION, "code": SHILIN, "hour": hour,
             "element": element, "value": value},
        )
    await session.commit()
    return publication


async def plant_forecast(session, hour, temperature, detected_at, sha, weather=None):
    result = await session.execute(
        text(
            "insert into forecast_publication (dataset_id, content_sha256, detected_at, payload_bytes) "
            "values ('F-D0047-061', :sha, :detected, 100) returning id"
        ),
        {"sha": sha, "detected": detected_at},
    )
    publication = result.scalar()
    rows = [("溫度", "Temperature", temperature)]
    if weather is not None:
        rows.append(("天氣現象", "Weather", weather))
    for element, measure, value in rows:
        await session.execute(
            text(
                "insert into forecast_reading (publication_id, township_code, township, "
                "element, measure, slot_start, slot_end, value) values (:p, :code, '士林區', "
                ":element, :measure, :hour, :end, :value)"
            ),
            {"p": publication, "code": SHILIN, "element": element, "measure": measure,
             "hour": hour, "end": hour + timedelta(hours=1), "value": value},
        )
    await session.commit()
    return publication


async def scenario(test_url):
    engine = create_async_engine(test_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        await seed.load(test_url)

    # ---- the ticket's central case: the observation for the hour has not landed -----------
    # Six o'clock has an observation; seven o'clock has only a forecast. Asking for seven must
    # return the forecast for seven, never the observation for six.
    async with Session() as session:
        await plant_observation(session, SIX, "28.0", SIX + timedelta(minutes=9), "a" * 64)
        await plant_forecast(session, SEVEN, "31", SIX, "b" * 64, weather="多雲")

    async with Session() as session:
        reading = await reading_for(session, SHILIN, SEVEN)
    assert reading.kind == "forecast", "expected the forecast for that hour, got {}".format(reading.kind)
    assert reading.hour == SEVEN
    assert reading.measures["temperature_c"] == "31"
    assert reading.provenance.time_label == "detected", "a forecast stamp is a detection time (D42)"
    print("  window: the previous hour's observation was not offered")

    # ---- the ordinary case: the observation has landed ------------------------------------
    async with Session() as session:
        await plant_observation(session, SEVEN, "29.5", SEVEN + timedelta(minutes=9), "c" * 64)
    async with Session() as session:
        reading = await reading_for(session, SHILIN, SEVEN)
    assert reading.kind == "observation", "the observation must win once it exists (D36)"
    assert reading.measures["temperature_c"] == "29.5"
    assert reading.station_id == STATION
    assert reading.provenance.time_label == "retrieved"
    print("  observation present: it wins over the forecast for the same hour")

    # ---- two versions of one hour: the later one answers ----------------------------------
    # Measured 2026-08-11: the observation is revised in place inside its own hour. Taking the
    # latest is an assumption flagged in _map.md, not a ruling — this test pins the current
    # behaviour so a ruling either way is a visible change.
    async with Session() as session:
        await plant_observation(session, SEVEN, "29.9", SEVEN + timedelta(minutes=40), "d" * 64)
    async with Session() as session:
        reading = await reading_for(session, SHILIN, SEVEN)
    assert reading.measures["temperature_c"] == "29.9", "expected the later revision of that hour"
    later_publication = reading.provenance.publication_id
    print("  revision: the later publication for that hour answered")

    # The earlier version is still there, which is what makes the assumption reversible and
    # what lets a round that pinned it still read as it did (D15).
    async with Session() as session:
        kept = await session.execute(
            text(
                "select count(distinct publication_id) from observation_reading "
                "where station_id = :s and observed_at = :hour"
            ),
            {"s": STATION, "hour": SEVEN},
        )
        assert kept.scalar() == 2, "an earlier version was overwritten"
    print("  revision: the earlier version is still stored")

    # ---- neither record: a stated absence, not a guess and not a crash --------------------
    empty_hour = SEVEN + timedelta(days=30)
    async with Session() as session:
        reading = await reading_for(session, SHILIN, empty_hour)
    assert reading.kind == "absent"
    assert not reading.present
    assert reading.absence_reason, "an absence has to say why"
    assert reading.measures == {}
    print("  absence: stated with a reason")

    # ---- an unknown township is an error, not an absence ----------------------------------
    async with Session() as session:
        try:
            await reading_for(session, "99999999", SEVEN)
            raise AssertionError("an unknown township code must not read as an absence")
        except TownshipUnknown:
            pass
    print("  unknown township: refused")

    # ---- a broken name join is an error, not an absence -----------------------------------
    # Since revision 0003 the join is on the geocode, so this can no longer be a misspelling.
    # It now means the ingest never ran for this code — still an error rather than an absence,
    # because reported as an absence it is indistinguishable from "no forecast this hour".
    async with Session() as session:
        await session.execute(text("delete from forecast_reading"))
        await session.execute(
            text("delete from observation_reading where observed_at = :hour"), {"hour": SEVEN}
        )
        await session.commit()
    async with Session() as session:
        try:
            await reading_for(session, SHILIN, SEVEN)
            raise AssertionError("a name that matches no forecast row must not read as an absence")
        except ForecastJoinBroken:
            pass
    print("  no forecast for the code at all: refused rather than reported as an absence")

    await engine.dispose()
    print("read path: observation, fallback, revision, absence and both refusals all hold")
    return later_publication


async def with_temporary_database():
    admin_url, test_url = urls()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text('drop database if exists "{}" with (force)'.format(TEST_DB)))
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
