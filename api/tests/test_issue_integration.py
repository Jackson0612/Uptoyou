#!/usr/bin/env python3
"""Ticket 18's issuing command, against a real PostgreSQL.

Run inside the stack:
    docker compose exec api python /srv/tests/test_issue_integration.py

The test builds its own database and drops it, so it never touches the stack's data.

The command is driven the way an operator drives it — as a subprocess, token read off
stdout — because the printed token is the whole interface: if parsing the output cannot
recover a working credential, the command has failed at its one job. The second run uses
``--principal`` and the assertion is D12's: exactly one principal row exists afterwards,
because a returning person gains a seat, never a second identity.
"""

import asyncio
import os
import subprocess
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from upto.auth import member_for  # noqa: E402

TEST_DB = "upto_issue_check"


def urls():
    live = os.environ["UPTO_DATABASE_URL"]
    head, _, _ = live.rpartition("/")
    return head + "/postgres", head + "/" + TEST_DB


def run_issue(test_url: str, *arguments: str) -> subprocess.CompletedProcess:
    environment = dict(
        os.environ,
        UPTO_DATABASE_URL=test_url,
        PYTHONPATH=SRC + os.pathsep + os.environ.get("PYTHONPATH", ""),
    )
    return subprocess.run(
        [sys.executable, "-m", "upto.issue", *arguments],
        env=environment,
        capture_output=True,
        text=True,
    )


def printed(stdout: str, label: str) -> str:
    for line in stdout.splitlines():
        if line.startswith(label + ": "):
            return line[len(label) + 2 :]
    raise AssertionError(f"stdout carries no '{label}: ' line:\n{stdout}")


async def counts(Session) -> tuple[int, int, int]:
    async with Session() as session:
        return tuple(
            [
                (await session.execute(text(f"select count(*) from {table}"))).scalar_one()
                for table in ("principal", "device_secret", "member")
            ]
        )


async def scenario(test_url: str) -> None:
    engine = create_async_engine(test_url, poolclass=None)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        circle_a = (
            await session.execute(
                text("insert into circle (name) values ('週三午餐') returning id")
            )
        ).scalar_one()
        circle_b = (
            await session.execute(
                text("insert into circle (name) values ('宿舍') returning id")
            )
        ).scalar_one()
        await session.commit()

    # First issue: a new principal, a seat, and a token that actually works.
    first = run_issue(test_url, str(circle_a), "Kevin")
    assert first.returncode == 0, first.stderr
    assert "shown once" in first.stdout, "the print-once warning is part of the interface"
    first_token = printed(first.stdout, "token")
    principal_id = int(printed(first.stdout, "principal"))
    member_a = int(printed(first.stdout, "member"))
    assert printed(first.stdout, "circle") == "週三午餐"
    async with Session() as session:
        assert await member_for(session, first_token, circle_a) == member_a
    assert await counts(Session) == (1, 1, 1)

    # The returning device: a seat in a second circle, and no second identity (D12).
    second = run_issue(test_url, str(circle_b), "阿凱", "--principal", str(principal_id))
    assert second.returncode == 0, second.stderr
    second_token = printed(second.stdout, "token")
    member_b = int(printed(second.stdout, "member"))
    assert int(printed(second.stdout, "principal")) == principal_id
    async with Session() as session:
        assert await member_for(session, second_token, circle_b) == member_b
    assert await counts(Session) == (1, 2, 2), (
        "the --principal run must not mint a second principal — D12's silent double-mint"
    )

    # An unknown circle refuses whole: exit 1, and not one row anywhere.
    refused = run_issue(test_url, "999999", "nobody")
    assert refused.returncode == 1, refused.stdout
    assert "no circle" in refused.stderr
    assert await counts(Session) == (1, 2, 2), "a refused issue left rows behind"

    # An unknown principal refuses the same way.
    refused = run_issue(test_url, str(circle_a), "nobody", "--principal", "999999")
    assert refused.returncode == 1, refused.stdout
    assert "no principal" in refused.stderr
    assert await counts(Session) == (1, 2, 2)

    # ---- D110's cap, amended 2026-08-20: the supported shape is ten people -------------------
    #
    # **Filling a circle to the cap and asking for one more, through the real CLI.** The number is
    # read from the module rather than written here: a test that restates a constant is a test that
    # passes after somebody changes the constant and forgets the rule.
    sys.path.insert(0, "/srv/src")
    from upto.issue import SEAT_CAP  # noqa: PLC0415 — read the shipped value, never a copy

    before = await counts(Session)
    for index in range(SEAT_CAP - 1):  # circle_a already holds Kevin
        filled = run_issue(test_url, str(circle_a), "seat{}".format(index))
        assert filled.returncode == 0, filled.stderr
    async with Session() as session:
        seats = (
            await session.execute(
                text("select count(*) from member where circle_id = :c"), {"c": circle_a}
            )
        ).scalar_one()
    assert seats == SEAT_CAP, "filling to the cap should have been allowed, got {}".format(seats)

    at_cap = await counts(Session)
    over = run_issue(test_url, str(circle_a), "eleventh")
    assert over.returncode == 1, over.stdout
    assert "supported shape is {}".format(SEAT_CAP) in over.stderr, over.stderr
    # **The refusal writes NOTHING — not a principal, not a device_secret, not a member.** The count
    # is taken before anything is minted for exactly this reason; the `IntegrityError` path rolls
    # back, and this one never starts. An orphan `device_secret` would be a credential belonging to
    # nobody, which is worse than a refused join.
    assert await counts(Session) == at_cap, (
        "a refused eleventh seat left rows behind: {} -> {}".format(at_cap, await counts(Session))
    )
    # And no token was printed, so nothing was handed out that could later be presented.
    assert "token:" not in over.stdout, over.stdout

    # **The other circle is unaffected** — the cap is per circle, not per principal or per install.
    still_fine = run_issue(test_url, str(circle_b), "又一位")
    assert still_fine.returncode == 0, still_fine.stderr

    # **A circle already over the cap keeps its seats and refuses the next one** — D110's
    # no-migration rule, which is the whole reason this reads as a refusal at join rather than as an
    # invariant on the table. Simulated by capping-then-inserting directly, because the CLI cannot
    # create the state the rule has to tolerate.
    async with Session() as session:
        oversized = (
            await session.execute(
                text("insert into circle (name) values ('over') returning id")
            )
        ).scalar_one()
        for index in range(SEAT_CAP + 5):
            principal = (
                await session.execute(text("insert into principal default values returning id"))
            ).scalar_one()
            await session.execute(
                text("insert into member (principal_id, circle_id, nickname) "
                     "values (:p, :c, :n)"),
                {"p": principal, "c": oversized, "n": "legacy{}".format(index)},
            )
        await session.commit()
    packed = await counts(Session)
    refused_over = run_issue(test_url, str(oversized), "one more")
    assert refused_over.returncode == 1, refused_over.stdout
    assert "already holds {} seats".format(SEAT_CAP + 5) in refused_over.stderr, refused_over.stderr
    assert await counts(Session) == packed, "the over-cap refusal wrote something"

    await engine.dispose()
    print(
        "ticket 18: the printed token is a working credential, --principal seats without a "
        "second identity, every refusal leaves no rows, and D110's ten-seat cap refuses the "
        "eleventh join while leaving an already-oversized circle exactly as it is"
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
