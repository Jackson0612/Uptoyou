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

    await engine.dispose()
    print(
        "ticket 18: the printed token is a working credential, --principal seats without a "
        "second identity, and every refusal leaves no rows"
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
