#!/usr/bin/env python3
"""Ticket 19's three endpoints, driven over HTTP shapes against a real PostgreSQL.

Run inside the stack:
    docker compose exec api python /srv/tests/test_api_rounds_integration.py

The test builds its own database and drops it, so it never touches the stack's data.

The requests go through the ASGI app itself — status codes, bodies and headers are the real
contract, not the router functions. Every ruled response shape is asserted: 401 for both
halves of a failed resolution (D67), 409 carrying the winner (D68), the quiet 200 (D70), the
cap's 409 (§3.0), the closed round's stored result (D69), and the roll chain landing whole
with D14's erasure observed after it.
"""

import asyncio
import os
import secrets as pysecrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

TEST_DB = "upto_api_rounds_check"
TAIPEI = timezone(timedelta(hours=8))


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


async def scenario(test_url: str) -> None:
    # The app reads UPTO_DATABASE_URL lazily per session, so pointing the environment at the
    # test database before the first request is what routes every endpoint call there.
    os.environ["UPTO_DATABASE_URL"] = test_url

    import httpx  # noqa: PLC0415

    from hashlib import sha256  # noqa: PLC0415

    from upto.main import app  # noqa: PLC0415

    engine = create_async_engine(test_url, poolclass=None)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.now(TAIPEI)
    slot_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    token = "t-" + pysecrets.token_urlsafe(24)

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
        circle = (
            await session.execute(
                text("insert into circle (name) values ('週三午餐') returning id")
            )
        ).scalar_one()
        other_circle = (
            await session.execute(
                text("insert into circle (name) values ('別人的圈子') returning id")
            )
        ).scalar_one()
        principal = (
            await session.execute(text("insert into principal default values returning id"))
        ).scalar_one()
        await session.execute(
            text(
                "insert into member (principal_id, circle_id, nickname) values (:p, :c, 'Kevin')"
            ),
            {"p": principal, "c": circle},
        )
        await session.execute(
            text("insert into device_secret (principal_id, secret_sha256) values (:p, :h)"),
            {"p": principal, "h": sha256(token.encode()).hexdigest()},
        )
        place_pub = (
            await session.execute(
                text(
                    "insert into place_publication (source, content_sha256, detected_at, "
                    "payload_bytes, entry_name, entry_bytes, scope) "
                    "values ('fda-97', repeat('b', 64), now(), 1000, 'x.csv', 1000, "
                    "'餐飲場所 / 臺北市') returning id"
                )
            )
        ).scalar_one()
        await session.execute(
            text(
                "insert into reference_place (publication_id, registry_no, origin, name, "
                "name_raw, address, address_raw, township_code, township_name) "
                "values (:pub, 'A-11111111-00001-1', 'reference', '雨中的店', '雨中的店', "
                "'x', 'x', '63000010', 'x')"
            ),
            {"pub": place_pub},
        )
        rainy = (
            await session.execute(
                text(
                    "insert into place (origin, registry_no) "
                    "values ('reference', 'A-11111111-00001-1') returning id"
                )
            )
        ).scalar_one()
        locals_ = []
        for name in ("巷口麵店", "小林拉麵", "阿宗麵線"):
            locals_.append(
                (
                    await session.execute(
                        text(
                            "insert into place (origin, circle_id, name) "
                            "values ('circle-local', :c, :n) returning id"
                        ),
                        {"c": circle, "n": name},
                    )
                ).scalar_one()
            )
        foreign_place = (
            await session.execute(
                text(
                    "insert into place (origin, circle_id, name) "
                    "values ('circle-local', :c, '外圈的店') returning id"
                ),
                {"c": other_circle},
            )
        ).scalar_one()
        weather_pub = (
            await session.execute(
                text(
                    "insert into forecast_publication "
                    "(dataset_id, content_sha256, detected_at, payload_bytes) "
                    "values ('F-D0047-061', repeat('a', 64), now(), 1000) returning id"
                )
            )
        ).scalar_one()
        await session.execute(
            text(
                "insert into forecast_reading (publication_id, township, township_code, "
                "element, slot_start, slot_end, measure, value) "
                "values (:pub, 'x', '63000010', '3小時降雨機率', :s, :e, "
                "'ProbabilityOfPrecipitation', '80')"
            ),
            {"pub": weather_pub, "s": slot_start, "e": slot_start + timedelta(hours=3)},
        )
        await session.commit()

    auth = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # D67: no token and a wrong token read the same 401.
        assert (await client.post(f"/circles/{circle}/rounds", json={})).status_code == 401
        assert (
            await client.post(
                f"/circles/{circle}/rounds",
                json={},
                headers={"Authorization": "Bearer wrong"},
            )
        ).status_code == 401

        # The open, defaulted: the hour is the hour the opener stands in (D73).
        opened = await client.post(f"/circles/{circle}/rounds", json={}, headers=auth)
        assert opened.status_code == 201, opened.text
        round_id = opened.json()["round_id"]
        assert opened.json()["target_hour_typed"] is False

        # D68: the losing open gets 409 carrying the winner.
        lost = await client.post(f"/circles/{circle}/rounds", json={}, headers=auth)
        assert lost.status_code == 409
        assert lost.json()["detail"]["open_round"]["round_id"] == round_id

        # Proposals: 201 new, 200 repeat (D70), 404 for a place this circle cannot see,
        # 409 for the fourth by one member (§3.0).
        for place in (rainy, locals_[0], locals_[1]):
            created = await client.post(
                f"/rounds/{round_id}/proposals", json={"place_id": place}, headers=auth
            )
            assert created.status_code == 201, created.text
        repeat = await client.post(
            f"/rounds/{round_id}/proposals", json={"place_id": rainy}, headers=auth
        )
        assert repeat.status_code == 200 and repeat.json()["pooled"] is True
        unseen = await client.post(
            f"/rounds/{round_id}/proposals",
            json={"place_id": foreign_place},
            headers=auth,
        )
        assert unseen.status_code == 404
        capped = await client.post(
            f"/rounds/{round_id}/proposals", json={"place_id": locals_[2]}, headers=auth
        )
        assert capped.status_code == 409

        # The roll: the whole chain in one transaction.
        rolled = await client.post(f"/rounds/{round_id}/roll", headers=auth)
        assert rolled.status_code == 200, rolled.text
        result = rolled.json()
        assert result["status"] == "closed"
        d1, d2 = result["dice"]
        assert 1 <= d1 <= 6 and 1 <= d2 <= 6 and result["sum"] == d1 + d2
        assert result["weights"] == {
            str(rainy): "0.8",
            str(locals_[0]): "1",
            str(locals_[1]): "1",
        }
        assert sum(result["allocation"].values()) == 36
        assert result["allocation"][str(result["winning_place_id"])] > 0
        # The panel's evidence rides in the result: the rainy place carries its factor in
        # D46's order, and the weather sentence stays behind ('none' visibility, D13).
        rainy_panel = result["panel"][str(rainy)]
        assert rainy_panel["factors"] == [
            {"channel": "contextual", "contributor": "weather", "effect": "0.8", "reason": None}
        ]
        assert rainy_panel["clamps"] == []
        assert result["panel"][str(locals_[0])]["factors"] == []

        # D69: the retry gets the stored result, dice and all, in the same shape.
        again = await client.post(f"/rounds/{round_id}/roll", headers=auth)
        assert again.status_code == 200
        assert again.json()["dice"] == result["dice"]
        assert again.json()["winning_place_id"] == result["winning_place_id"]
        assert again.json()["weights"] == result["weights"]
        assert again.json()["allocation"] == result["allocation"]

        # Proposing into a closed round is a 409, not a quiet anything.
        late = await client.post(
            f"/rounds/{round_id}/proposals", json={"place_id": locals_[2]}, headers=auth
        )
        assert late.status_code == 409

    # D14, observed through the endpoint path: the close erased authorship, kept the pool.
    async with Session() as session:
        authored = (
            await session.execute(
                text(
                    "select count(*) from proposal "
                    "where round_id = :r and member_id is not null"
                ),
                {"r": round_id},
            )
        ).scalar_one()
        pool_size = (
            await session.execute(
                text("select count(*) from proposal where round_id = :r"), {"r": round_id}
            )
        ).scalar_one()
    assert authored == 0 and pool_size == 3

    from upto.db import dispose_all  # noqa: PLC0415

    await dispose_all()
    await engine.dispose()
    print(
        "ticket 19: both 401 halves read the same, the losing open carries the winner, the "
        "pool rules answer in status codes, and the roll chain lands whole with the erasure"
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
