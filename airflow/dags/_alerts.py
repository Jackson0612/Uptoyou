"""A10 — a failed task says so on a phone, once, in one sentence.

*Owner-ruled 2026-08-19.*

**The question.** Every DAG in this repository is nocturnal: 19:00–20:20 UTC is 03:00–04:20 in
Taipei, and the preference erasure runs at 05:00. A red task at 03:20 is discovered when somebody
opens `localhost:8081`, which on a good week is the following evening. `ingest_run`'s daily
heartbeat makes a silently broken source *findable*; it does not make it *noticed*.

So one `on_failure_callback`, shared by every DAG, sending one Telegram message. Not a dashboard,
not a digest, not a second channel for successes — the successes are already in the ledger and a
channel that speaks every night is a channel nobody reads.

**A missing Connection warns and never fails, and this is the load-bearing rule.** The alert is
*about* a failure; an alert that can itself fail turns one red task into two, and the second one
tells you nothing about the pipeline. So every path here is wrapped: no Connection, no network, a
4xx from Telegram, a malformed chat id — each prints a line to the task log and returns. A fresh
clone with no token, and `tools/split_boot_check.sh`'s isolated stack, both run with alerting simply
absent, which is the correct behaviour for a stack nobody is watching.

**What the message may contain, and why this is not a formality.** The text leaves this machine.
`_database_url()` in the ingest DAGs builds `postgresql+asyncpg://user:PASSWORD@db:5432/…`, and a
connection failure's traceback contains it — so a callback that forwarded the exception text
verbatim would post `POSTGRES_PASSWORD` into a chat, from the one code path that only ever runs when
something has already gone wrong and nobody is watching. Three redactions run, in this order, and
the belt-and-braces is deliberate:

1. Airflow's own `redact`, which knows the values of every Connection field this process has read.
2. A regex over `scheme://anything:anything@host`, which catches a URL Airflow never saw.
3. The literal values of the named bootstrap environment variables — including the bot token
   itself, which must never appear in a message it is the transport for.

**Rejected: sending only the identity and «read the log».** It leaks nothing at all and it is what a
first draft of this file did. The cost is that the single most useful sentence — *the row count
collapsed: 12 rows against 14513* — is the sentence a person needs to decide whether to get out of
bed, and withholding it makes the alert a doorbell. Redaction plus a cap keeps the sentence and
closes the leak.

**Rejected: the `apache-airflow-providers-telegram` provider.** One `urllib` POST against a
documented endpoint, against a dependency in the image, a hook to learn, and a second place for the
Connection shape to be defined. Every other outbound call in this repository is stdlib for the same
reason.

**No log URL.** The UI is `localhost:8081`, which is not reachable from the phone the message
arrives on, so a link would be a dead end dressed as an answer. The message carries the log's path
inside the container instead, which is what somebody at a keyboard actually needs.

The Connection is `telegram_alerts`, written delete-then-add by `airflow/init.sh`:
`--conn-type http --conn-host api.telegram.org --conn-login <chat_id> --conn-password <bot token>`.
Rotating the token is `init.sh`'s job — `docker compose up airflow-init --force-recreate --no-deps`
— the same three-places rule the CWA key carries in `CLAUDE.md`.

Tested by `app/api/tests/test_alerts.py` — `compose_message()` and `scrub()` are pure and need no
Airflow, no network and no database.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

CONNECTION_ID = "telegram_alerts"
ENDPOINT = "https://api.telegram.org/bot{}/sendMessage"

# The message is one sentence plus identity. Telegram's own limit is 4096 characters; this cap is
# about the *reader*, who is holding a phone at 03:20, and about how much of a traceback can be
# forwarded before the redaction has more surface than it can be trusted over.
MESSAGE_CAP = 700
DETAIL_CAP = 320
TIMEOUT_SECONDS = 10

# Bootstrap secrets whose literal values are scrubbed out of any detail text. These are exactly the
# names `.env.example` lists, and the airflow services carry them in their environment — so a
# traceback that interpolated one is a traceback that would post it. `TELEGRAM_` is not among them
# because the token arrives from the Connection, not the environment; it is scrubbed separately and
# unconditionally.
SECRET_ENVIRONMENT_NAMES = (
    "POSTGRES_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "AIRFLOW_FERNET_KEY",
    "AIRFLOW_JWT_SECRET",
    "AIRFLOW_ADMIN_PASSWORD",
    "UPTO_CWA_API_KEY",
)

# `scheme://user:password@host` — the shape `_database_url()` builds and the shape a driver puts in
# its exception. Non-greedy, and the password class excludes `/` and whitespace so a URL later in
# the same line cannot be swallowed.
CREDENTIAL_URL = re.compile(r"(?P<scheme>[a-zA-Z0-9+.\-]+://)[^/\s:@]+:[^/\s@]+@")

REDACTED = "***"


def scrub(text: str, extra: tuple[str, ...] = ()) -> str:
    """Remove credentials from text that is about to leave this machine.

    Pure, and deliberately not dependent on Airflow: the masker is asked for first inside
    `send_failure_alert`, and this function is the floor under it — the part that still works when
    the masker has never seen the value, which is the case for anything assembled at run time.
    """
    if not text:
        return ""
    cleaned = CREDENTIAL_URL.sub(lambda m: m.group("scheme") + REDACTED + ":" + REDACTED + "@", text)
    values = [os.environ.get(name) for name in SECRET_ENVIRONMENT_NAMES]
    values.extend(extra)
    # Longest first: a short secret that is a substring of a longer one must not carve the longer
    # one into pieces that then fail to match.
    for value in sorted((v for v in values if v and len(v) >= 4), key=len, reverse=True):
        cleaned = cleaned.replace(value, REDACTED)
    return cleaned


def compose_message(
    dag_id: str,
    task_id: str,
    run_id: str,
    try_number: int,
    max_tries: int,
    detail: str,
    log_path: str = "",
) -> str:
    """The whole message. Pure — no Airflow, no network.

    One line of identity, one line of what happened, one line of where to look. In that order
    because the first line is all that shows in a phone's notification.
    """
    # **`max_tries` is the number of RETRIES, so the total is one more.** `retries: 2` gives
    # `max_tries = 2` and `try_number` counting 1, 2, 3 — so reading `max_tries` as the total
    # printed "attempt 3 of 2", which reads as a bug in the alert rather than the third and last
    # attempt it actually was.
    attempts = ("attempt {} of {}".format(try_number, max_tries + 1) if max_tries
                else "attempt {}".format(try_number))
    head = "upto: {} / {} FAILED ({})".format(dag_id, task_id, attempts)
    body = [head, "", "run: {}".format(run_id)]
    if detail:
        clipped = detail if len(detail) <= DETAIL_CAP else detail[: DETAIL_CAP - 1] + "…"
        body.append(clipped)
    if log_path:
        body.append("")
        body.append("log: {}".format(log_path))
    message = "\n".join(body)
    return message if len(message) <= MESSAGE_CAP else message[: MESSAGE_CAP - 1] + "…"


def _log_path(dag_id: str, run_id: str, task_id: str, try_number: int) -> str:
    """Where the log actually is inside the airflow containers.

    Not a URL. The UI is on `localhost:8081`, unreachable from the phone this arrives on, so a link
    would be a dead end dressed as an answer. This path is what somebody at a keyboard needs, and it
    is the layout measured on this stack 2026-08-19 while reading A9's own run.
    """
    return "/opt/airflow/logs/dag_id={}/run_id={}/task_id={}/attempt={}.log".format(
        dag_id, run_id, task_id, try_number)


def send_failure_alert(context) -> None:
    """`on_failure_callback` for every DAG in this repository. Never raises, whatever happens.

    Airflow calls this after the retries are spent, so one failed task is one message.
    """
    try:
        _send(context)
    except BaseException as problem:  # noqa: BLE001 — see the docstring: it may not raise
        # Printed, so it lands in the task log of the task that already failed. An alert that
        # fails is worth knowing about and is not worth a second red task.
        print("alert: could not send the failure alert ({}: {}) — the task's own failure above is "
              "the one that matters".format(type(problem).__name__, problem))


def _send(context) -> None:
    from airflow.hooks.base import BaseHook

    instance = context.get("task_instance")
    dag_id = getattr(instance, "dag_id", "") or str(context.get("dag", ""))
    task_id = getattr(instance, "task_id", "") or ""
    run_id = getattr(instance, "run_id", "") or ""
    try_number = getattr(instance, "try_number", 0) or 0
    max_tries = getattr(instance, "max_tries", 0) or 0

    raw = context.get("exception")
    detail = "" if raw is None else "{}: {}".format(type(raw).__name__, raw)

    # Airflow's own masker knows every Connection value this process has read — including the bot
    # token below, once the Connection has been fetched. Asked for first and tolerated absent: the
    # import path moved between Airflow 2 and 3 (`airflow.utils.log.secrets_masker` does not exist
    # in 3.0.2, measured), and `scrub` is the floor that does not depend on it.
    try:
        from airflow.sdk.execution_time.secrets_masker import redact

        detail = str(redact(detail))
    except Exception:  # noqa: BLE001 — an absent masker is not a reason to send nothing
        pass

    try:
        connection = BaseHook.get_connection(CONNECTION_ID)
    except Exception as missing:  # noqa: BLE001
        print("alert: no `{}` Connection ({}), so no message was sent — alerting is off on this "
              "stack, which is the designed state for one nobody is watching".format(
                  CONNECTION_ID, type(missing).__name__))
        return

    token = (connection.password or "").strip()
    chat_id = (connection.login or "").strip()
    if not token or not chat_id:
        print("alert: the `{}` Connection is missing its {} — nothing sent".format(
            CONNECTION_ID, "password (bot token)" if not token else "login (chat id)"))
        return

    detail = scrub(detail, extra=(token,))
    message = compose_message(
        dag_id, task_id, run_id, try_number, max_tries, detail,
        _log_path(dag_id, run_id, task_id, try_number))

    payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT.format(token),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            code = response.status
    except urllib.error.HTTPError as refused:
        # **`HTTPError` before `URLError`, because it is a subclass of it.** Telegram said no — a
        # wrong chat id, a revoked token — and that is a different thing to fix from "no network",
        # so it gets its own line. The body is read and *not* forwarded: it echoes the request.
        print("alert: Telegram refused the message (HTTP {}) — check the `{}` Connection's chat id "
              "and token; the task's own failure above is unaffected".format(
                  refused.code, CONNECTION_ID))
        return
    except urllib.error.URLError as unreachable:
        print("alert: could not reach Telegram ({}) — nothing sent, and the task's own failure "
              "above is unaffected".format(unreachable.reason))
        return
    print("alert: failure alert sent for {} / {} (HTTP {})".format(dag_id, task_id, code))
