#!/usr/bin/env python3
"""H14's item-11 test, against a real PostgreSQL.

Run inside the stack:
    docker compose exec api python /srv/tests/test_place_ingest_integration.py

**Not yet run. Written against the schema and unverified.** No database was reachable when
this was written — another session held the stack — so every claim below is a claim about what
the code should do, not a report of what it did. It is committed unrun on purpose: an assertion
written before the first live run is one that has not been fitted to whatever the first live run
happened to produce.

H14 names this test, and names what it must not settle for:

    "run the ingest, run it again against an unchanged file, and assert **one** publication row
    and 232,212 data rows rather than two and 464,424 — with the short-circuit **deliberately
    disabled**, so that what is being tested is the constraint rather than the scheduler's good
    behaviour. A test that passes only because the ingest declined to write proves nothing about
    this hazard."

That is the third scenario below. The row count is this ingest's own — 臺北市 `餐飲場所`, not the
nationwide 232,212 the hazard quotes — and the fixture is small, because the property under test
is the key rather than the volume.

**How to show these assertions discriminate, which is the step item 10's test took and this one
has not.** Change the publication key from the content hash to the run: in `0003`, replace the
unique constraint `(source, content_sha256)` with `(source, detected_at)`, and the conflict target
in `fda_store.CLAIM_PUBLICATION` with it. That is D18's fallback, which D35 rejects for this
source. Under it the second run mints a second publication and writes the same places again, so
`test_an_unchanged_file_produces_no_duplicate` must fail with *expected one publication, got 2*.
A test that cannot fail under the wrong key is the test H14 threw out.

The test builds its own database and drops it, so it never touches the stack's data.
"""

import asyncio
import io
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from upto.ingest import fda  # noqa: E402
from upto.ingest.fda_store import PlaceStore  # noqa: E402
from upto.ingest.run_places import ingest_archive  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
TEST_DB = "upto_item11_check"

HEADER = "公司或商業登記名稱,公司統一編號,業者地址,食品業者登錄字號,登錄項目"

# Three rows: one ordinary, one carrying the defects the real file carries (H25 — a fixture
# with no defect never reaches the code that cleans one), and one real address that resolves
# to no township at all.
ROWS = [
    '"福利麵包食品有限公司","11820764","台北市信義區菸廠路88號B1","A-111820764-00022-1","餐飲場所"',
    '"全家便利商店股份有限公司","23060248","臺北市中正區忠孝西路一段４９號Ｂ１","A-123060248-13440-5","餐飲場所"',
    '"某小吃店","20003433","台北市長安東路一段58號","A-200034336-00001-9","餐飲場所"',
]
CHANGED_ROWS = ROWS[:2] + [
    '"某小吃店","20003433","台北市中山區長安東路一段58號","A-200034336-00001-9","餐飲場所"',
]

PLACES = len(ROWS)


def archive(rows, stamp, detected_at):
    body = "\r\n".join([HEADER] + rows) + "\r\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(zipfile.ZipInfo("97_2.csv", date_time=stamp), b"\xef\xbb\xbf" + body.encode("utf-8"))
    return fda.read_archive(buffer.getvalue(), detected_at)


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


async def counts(Session):
    async with Session() as session:
        publications = await session.execute(text("select count(*) from place_publication"))
        places = await session.execute(text("select count(*) from reference_place"))
        return publications.scalar(), places.scalar()


async def scenario(test_url: str) -> None:
    engine = create_async_engine(test_url, poolclass=None)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    july = archive(ROWS, (2026, 7, 3, 9, 16, 50), datetime(2026, 8, 10, 3, 0, tzinfo=TAIPEI))
    august = archive(CHANGED_ROWS, (2026, 8, 3, 10, 41, 40), datetime(2026, 8, 11, 3, 0, tzinfo=TAIPEI))

    # 1 — the first run stores a publication and its places.
    async with Session() as session:
        first = await ingest_archive(PlaceStore(session), july)
    assert first.stored, "the first run must store a publication"
    assert first.parsed
    assert first.rows_held == PLACES, "expected {} places, got {}".format(PLACES, first.rows_held)
    assert len(first.unresolved) == 1, "the address with no district must be reported"
    assert first.alarms == [], "nothing to disagree with on a first run"
    assert await counts(Session) == (1, PLACES)

    # 2 — the same file again. Nothing is written, nothing is parsed, and the run succeeds.
    async with Session() as session:
        again = await ingest_archive(PlaceStore(session), july)
    assert not again.stored, "an unchanged file must not store a second publication"
    assert not again.parsed, "an unchanged file must not be parsed at all (D34)"
    assert again.exit_code() == 0, "a no-op is a success, not a warning"
    assert await counts(Session) == (1, PLACES)

    # 3 — H14's own scenario: run it again with the short-circuit **disabled**, so the
    # constraint is what stops the duplicate rather than this module's good behaviour.
    async with Session() as session:
        forced = await ingest_archive(PlaceStore(session), july, force_parse=True)
    assert forced.parsed, "force-parse must actually parse"
    assert not forced.stored, "no second publication may be created for the same content"
    assert forced.rows_held == PLACES, "the places must not have doubled: {}".format(forced.rows_held)
    publications, places = await counts(Session)
    assert publications == 1, "expected one publication, got {}".format(publications)
    assert places == PLACES, "expected {} places, got {}".format(PLACES, places)

    # 4 — the township came out of the address, and the row that had none was stored anyway.
    async with Session() as session:
        result = await session.execute(
            text(
                "select registry_no, township_code, township_name, origin, address, address_raw "
                "from reference_place order by registry_no"
            )
        )
        rows = {row.registry_no: row for row in result}
    assert rows["A-111820764-00022-1"].township_code == "63000020", "信義區 by address (D27)"
    assert rows["A-123060248-13440-5"].township_code == "63000050", "中正區, full-width folded"
    assert rows["A-123060248-13440-5"].address == "臺北市中正區忠孝西路一段49號B1"
    assert rows["A-123060248-13440-5"].address_raw.endswith("４９號Ｂ１"), "the raw string survives (H24)"
    assert rows["A-200034336-00001-9"].township_code is None, "no district in the address"
    assert rows["A-200034336-00001-9"].township_name is None
    for row in rows.values():
        assert row.origin == "reference", "D28: the origin is recorded on every row"

    async with Session() as session:
        recorded = await session.execute(
            text("select place_rows, unresolved_township_rows, scope, archive_stamp from place_publication")
        )
        publication = recorded.fetchone()
    assert publication.place_rows == PLACES
    assert publication.unresolved_township_rows == 1
    assert publication.scope == fda.SCOPE
    assert publication.archive_stamp == datetime(2026, 7, 3, 9, 16, 50, tzinfo=TAIPEI), (
        "the stamp is stored as the label, with its zone (H17)"
    )

    # 5 — a genuinely new file. Both publications survive; the earlier rows do not move,
    # because a round's snapshot may already have pinned one (D15).
    async with Session() as session:
        second = await ingest_archive(PlaceStore(session), august)
    assert second.stored, "changed content is a new publication"
    assert second.alarms == [], "both signals moved together, which is agreement"
    publications, places = await counts(Session)
    assert publications == 2, "expected two publications, got {}".format(publications)
    assert places == 2 * PLACES, "expected {} places, got {}".format(2 * PLACES, places)

    async with Session() as session:
        pinned = await session.execute(
            text(
                "select p.detected_at, r.township_code from reference_place r "
                "join place_publication p on p.id = r.publication_id "
                "where r.registry_no = :registry order by p.detected_at"
            ),
            {"registry": "A-200034336-00001-9"},
        )
        versions = pinned.fetchall()
    assert len(versions) == 2
    assert versions[0].township_code is None, "the earlier row was rewritten"
    assert versions[1].township_code == "63000040", "the later row reads its township (中山區)"

    # 6 — re-running the *first* file after the second one must still change nothing.
    async with Session() as session:
        rerun = await ingest_archive(PlaceStore(session), july)
    assert not rerun.stored
    assert not rerun.parsed
    assert await counts(Session) == (2, 2 * PLACES)

    await engine.dispose()
    print("H14/item 11: one publication per content hash; a forced re-parse writes no duplicate")


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
        # The township reference table has to exist before a place can point at it — the
        # foreign key is D27's, and ticket 06's seed is where the twelve codes live.
        from upto.seed.township_station import load

        await load(test_url)
        await scenario(test_url)
    finally:
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as connection:
            await connection.execute(text('drop database if exists "{}" with (force)'.format(TEST_DB)))
        await admin.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(with_temporary_database()))
