#!/usr/bin/env python3
"""D75/D76's backfill, against a real PostgreSQL and a stub model.

Run inside the stack:
    docker compose exec api python /srv/tests/test_classify_integration.py

The test builds its own database and drops it, so it never touches the stack's data.

**The model is stubbed on purpose.** What is under test is the schema half — materialising
a township (D76), writing provenance with the value (D39), leaving a refused answer
unwritten (D63), and resuming where an interrupted run stopped. Whether the model answers
*well* is the evaluation rounds' question and needs a fixed set, not a live service.
"""

import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from upto.classify import run as runner  # noqa: E402

TEST_DB = "upto_classify_check"

NAMES = {
    "A-1": "啟祥早餐店",
    "A-2": "老捌麻辣食堂",
    "A-3": "旨王開發有限公司",
    "A-4": "一階堂",
}
# What the stub model answers for each name. A-4's answer is outside D38's list on purpose.
ANSWERS = {"啟祥早餐店": "早餐", "老捌麻辣食堂": "火鍋", "旨王開發有限公司": "其他", "一階堂": "拉麵"}


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


async def scenario(test_url: str) -> None:
    os.environ["UPTO_DATABASE_URL"] = test_url
    engine = create_async_engine(test_url, poolclass=None)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        for code, name in (("63000010", "松山區"), ("63000020", "信義區")):
            await session.execute(
                text(
                    "insert into township_station "
                    "(township_code, township_name, station_id, station_name, resolution) "
                    "values (:c, :n, 'C0A980', '測試站', 'town_code')"
                ),
                {"c": code, "n": name},
            )
        publication = (
            await session.execute(
                text(
                    "insert into place_publication (source, content_sha256, detected_at, "
                    "payload_bytes, entry_name, entry_bytes, scope) "
                    "values ('fda-97', repeat('b', 64), now(), 1000, 'x.csv', 1000, "
                    "'餐飲場所 / 臺北市') returning id"
                )
            )
        ).scalar_one()
        for registry_no, name in NAMES.items():
            await session.execute(
                text(
                    "insert into reference_place (publication_id, registry_no, origin, name, "
                    "name_raw, address, address_raw, township_code, township_name) "
                    "values (:pub, :no, 'reference', :n, :n, 'x', 'x', '63000010', '松山區')"
                ),
                {"pub": publication, "no": registry_no, "n": name},
            )
        # A neighbouring township, so the backfill is shown to stay inside its own scope.
        await session.execute(
            text(
                "insert into reference_place (publication_id, registry_no, origin, name, "
                "name_raw, address, address_raw, township_code, township_name) "
                "values (:pub, 'B-1', 'reference', '信義區的店', '信義區的店', 'x', 'x', "
                "'63000020', '信義區')"
            ),
            {"pub": publication},
        )
        await session.commit()

    # The stub: answers from the table above, and records what it was asked.
    asked = []

    def stub(prompt):
        asked.append(prompt)
        for name, answer in ANSWERS.items():
            if name in prompt:
                return answer
        raise AssertionError("the runner asked about a name the test never seeded")

    runner.ask = stub
    runner.available = lambda: True
    runner.MODEL = "stub-model:test"

    assert await runner.main("63000010") == 0

    async with Session() as session:
        rows = (
            await session.execute(
                text(
                    "select p.registry_no, p.category, p.category_model, "
                    "p.category_prompt_version, p.category_generated_at "
                    "from place p where p.origin = 'reference' order by p.registry_no"
                )
            )
        ).all()
    by_registry = {row.registry_no: row for row in rows}

    # D76: the township was materialised — and only this township.
    assert set(by_registry) == set(NAMES), f"materialised the wrong set: {sorted(by_registry)}"

    # D39: the value travels with its provenance, always both or neither.
    assert by_registry["A-1"].category == "早餐"
    assert by_registry["A-2"].category == "火鍋"
    assert by_registry["A-1"].category_model == "stub-model:test"
    assert by_registry["A-1"].category_prompt_version.startswith("v1-")
    assert by_registry["A-1"].category_generated_at is not None

    # D63: an answer outside D38's list is not written and not coerced.
    assert by_registry["A-4"].category is None, "拉麵 was written despite being off the list"
    assert by_registry["A-4"].category_model is None

    # The prompt the model actually received carries the ladder, not just the name.
    assert any("判斷順序" in prompt for prompt in asked)

    # A second run is a near no-op: only the refused row is retried, nothing is rewritten.
    asked.clear()
    assert await runner.main("63000010") == 0
    assert len(asked) == 1, f"a second pass re-asked {len(asked)} names instead of the one refused"

    # The model being off is an ordinary outcome, distinct from a failure, and writes nothing.
    runner.available = lambda: False
    assert await runner.main("63000010") == 3

    await engine.dispose()
    print(
        "classify: the township materialises inside its own scope, provenance travels with "
        "every value, an off-list answer stays unwritten, and a second pass retries only it"
    )


async def with_temporary_database() -> int:
    admin_url, test_url = urls()
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text('drop database if exists "{}"'.format(TEST_DB)))
        await connection.execute(text('create database "{}"'.format(TEST_DB)))
    await admin.dispose()

    try:
        environment = dict(os.environ, UPTO_DATABASE_URL=test_url)
        for attempt in (1, 2):
            migrate = subprocess.run(
                ["alembic", "upgrade", "head"], cwd="/srv", env=environment, capture_output=True
            )
            if migrate.returncode != 0:
                print(migrate.stderr.decode("utf-8", "replace"), file=sys.stderr)
                return 2
            if attempt == 2:
                noise = migrate.stdout.decode("utf-8", "replace") + migrate.stderr.decode(
                    "utf-8", "replace"
                )
                assert "Running upgrade" not in noise, (
                    "the second `alembic upgrade head` ran a migration:\n" + noise
                )
        await scenario(test_url)
    finally:
        admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as connection:
            await connection.execute(
                text('drop database if exists "{}" with (force)'.format(TEST_DB))
            )
        await admin.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(with_temporary_database()))
