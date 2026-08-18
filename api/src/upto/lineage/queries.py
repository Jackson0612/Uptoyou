"""MVP item 14 — where a reading came from, answered over stored rows only.

The reveal panel answers *why this place?* for a person. This answers it for a model, over the
same records. At this point the pipeline has written ingest rows only, so this covers ingest —
there are no weight contributions yet.

**H20 is designed in here rather than added later, and that is the whole reason this module is
narrow.** The hazard is that a lineage tool is built to be *useful*, and the most useful answer
is the complete one: the trail runs into `weight_contribution`, whose `private`-channel rows
carry a member and a reason its owner was promised nobody would see (D13, §3.0). Answered
completely, *"why did this place lose?"* is H3 firing through a door nobody watches — it is not
a browser payload, so the network tab that would catch H3 never sees it.

**So the boundary is structural, not a filter applied at the end.** These functions can only
read four tables — publications, readings, runs and the township map. **There is no query here
that mentions a member, a channel, or a weight**, and a test asserts the tool refuses rather
than relying on nothing having asked. When the weight engine lands, the aggregate-only rule
H20 states is a new function with its own test, not a widened one of these.

**Nothing is computed and presented as recorded.** Every field returned is a column. Where a
number would have to be derived, the answer says so instead — which is why a publication's
reading count is queried rather than remembered.

**A forecast's timestamp is a detection time** (D42): CWA never says when a forecast was
published, so every answer carries the label with the value and never the value alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# `text` is imported inside each function that runs SQL. The refusal and the label rules are
# pure, and a test that needs neither a database nor its driver is the test H20 asks for.

FORECAST_DATASET = "F-D0047-061"
OBSERVATION_DATASET = "O-A0001-001"

# The only tables this module may read. Stated as data so the test can assert it, rather than
# left as a property of whatever the queries happen to say today.
READABLE_TABLES = frozenset(
    {
        "forecast_publication",
        "forecast_reading",
        "observation_publication",
        "observation_reading",
        "place_publication",
        "reference_place",
        "ingest_run",
        "township_station",
    }
)

# Named so the refusal can quote them. H20's boundary is about these three ideas.
FORBIDDEN_SUBJECTS = ("member", "private channel", "weight", "contribution", "reason")


class LineageRefused(PermissionError):
    """The question asks for something H20 forbids, and the refusal is the answer.

    Raised rather than answered partially, because a partial answer to "why did this place
    lose" is the shape that looks like the feature working.
    """


@dataclass
class Answer:
    """Every answer carries what it was asked and which rows it stands on."""

    question: str
    found: bool
    detail: Dict[str, Any] = field(default_factory=dict)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    note: Optional[str] = None


def _time_label(dataset_id: str) -> str:
    """A forecast stamp is a detection time; an observation's is when we retrieved it."""
    return "detected_at" if dataset_id == FORECAST_DATASET else "retrieved_at"


READING_SOURCE_FORECAST = """
select p.id as publication_id, p.dataset_id, p.content_sha256, p.detected_at, p.payload_bytes,
       r.township_code, r.township, r.element, r.measure, r.slot_start, r.slot_end, r.value,
       run.id as run_id, run.outcome, run.invoked_by, run.started_at, run.finished_at
from forecast_reading r
join forecast_publication p on p.id = r.publication_id
left join ingest_run run on run.forecast_publication_id = p.id
where r.township_code = :township_code and r.slot_start = :hour
  and r.element = :element and r.measure = :measure
order by p.detected_at desc
"""

READING_SOURCE_OBSERVATION = """
select p.id as publication_id, p.dataset_id, p.content_sha256, p.detected_at, p.payload_bytes,
       r.station_id, r.station_name, r.town_code, r.observed_at, r.element, r.value,
       run.id as run_id, run.outcome, run.invoked_by, run.started_at, run.finished_at
from observation_reading r
join observation_publication p on p.id = r.publication_id
left join ingest_run run on run.observation_publication_id = p.id
where r.station_id = :station_id and r.observed_at = :hour and r.element = :element
order by p.detected_at desc
"""


async def forecast_reading_source(
    session, township_code: str, hour: datetime, element: str, measure: str
) -> Answer:
    """Every stored version of one forecast reading, newest first.

    Plural on purpose: the same described hour is published repeatedly and D18 keeps every
    version, so "where did this come from" has more than one true answer and the caller is
    entitled to see that rather than be handed the latest as though it were the only one.
    """
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(READING_SOURCE_FORECAST),
            {"township_code": township_code, "hour": hour, "element": element, "measure": measure},
        )
    ).mappings().all()
    label = _time_label(FORECAST_DATASET)
    return Answer(
        question="forecast reading source",
        found=bool(rows),
        detail={
            "township_code": township_code,
            "hour": hour.isoformat(),
            "element": element,
            "measure": measure,
            "versions": len(rows),
            "time_label": label,
            "time_label_note": (
                "the forecast carries no publication time, so this is when the ingest first "
                "saw the content — never present it as a publication time (D42)"
            ),
        },
        rows=[
            {
                "publication_id": row["publication_id"],
                "dataset_id": row["dataset_id"],
                "content_sha256": row["content_sha256"],
                label: row["detected_at"].isoformat(),
                "value": row["value"],
                "slot_start": row["slot_start"].isoformat(),
                "slot_end": row["slot_end"].isoformat() if row["slot_end"] else None,
                "township": row["township"],
                "run": _run_of(row),
            }
            for row in rows
        ],
        note=None if rows else "no stored forecast reading matches that township, hour and measure",
    )


async def observation_reading_source(
    session, station_id: str, hour: datetime, element: str
) -> Answer:
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(READING_SOURCE_OBSERVATION),
            {"station_id": station_id, "hour": hour, "element": element},
        )
    ).mappings().all()
    label = _time_label(OBSERVATION_DATASET)
    return Answer(
        question="observation reading source",
        found=bool(rows),
        detail={
            "station_id": station_id,
            "hour": hour.isoformat(),
            "element": element,
            "versions": len(rows),
            "time_label": label,
            "time_label_note": (
                "the observation states its own ObsTime, which is the hour described; this "
                "stamp is only when the ingest retrieved it"
            ),
        },
        rows=[
            {
                "publication_id": row["publication_id"],
                "dataset_id": row["dataset_id"],
                "content_sha256": row["content_sha256"],
                label: row["detected_at"].isoformat(),
                "observed_at": row["observed_at"].isoformat(),
                "value": row["value"],
                "station_name": row["station_name"],
                "town_code": row["town_code"],
                "run": _run_of(row),
            }
            for row in rows
        ],
        note=None if rows else "no stored observation matches that station, hour and element",
    )


def _run_of(row) -> Optional[Dict[str, Any]]:
    """The run that wrote a publication, where one is recorded.

    Nullable rather than assumed: the publications written before `ingest_run` existed have no
    run, and inventing one would be exactly the *computed and presented as recorded* failure
    this module refuses.
    """
    if row["run_id"] is None:
        return None
    return {
        "run_id": row["run_id"],
        "outcome": row["outcome"],
        "invoked_by": row["invoked_by"],
        "started_at": row["started_at"].isoformat(),
        "finished_at": row["finished_at"].isoformat(),
    }


RUN = """
select id, source, started_at, finished_at, outcome, rows_written, detail, invoked_by,
       forecast_publication_id, observation_publication_id, place_publication_id
from ingest_run where id = :run_id
"""

# Two statements rather than one with `(:source is null or source = :source)`. asyncpg cannot
# infer the type of a parameter that appears only against NULL and a text column, and fails with
# AmbiguousParameterError — a driver limit rather than bad SQL. A cast would work; two plain
# statements read better than explaining a cast.
RUN_HISTORY_ALL = """
select id, source, started_at, finished_at, outcome, rows_written, invoked_by
from ingest_run
order by started_at desc, id desc
limit :limit
"""

RUN_HISTORY_FOR_SOURCE = """
select id, source, started_at, finished_at, outcome, rows_written, invoked_by
from ingest_run
where source = :source
order by started_at desc, id desc
limit :limit
"""


async def run_detail(session, run_id: int) -> Answer:
    """What one run did — including a run that wrote nothing.

    A no-change run is the ordinary outcome, about twenty of twenty-four daily forecast runs
    (D42), and ticket 09 requires it to be **lineage worth pointing at rather than an
    absence**. It is a row here, described as such, and distinguishable from a run that failed.
    """
    from sqlalchemy import text

    row = (await session.execute(text(RUN), {"run_id": run_id})).mappings().first()
    if row is None:
        return Answer(
            question="run detail",
            found=False,
            detail={"run_id": run_id},
            note="no run with that id is recorded",
        )
    publication_id = (
        row["forecast_publication_id"]
        or row["observation_publication_id"]
        or row["place_publication_id"]
    )
    written = None
    if publication_id is not None:
        # **`rows_newly_stored`, not `rows_written`, and the rename is the point** (H32's second
        # half, closed by ruling 2026-08-18). The column counts rows the database *accepted* as
        # new. A rows-only replay rebuilds every row of a table and records `no_change` with a
        # count of 0, because the claim short-circuits on a hash already held — so a reader
        # summing "rows written" sees a backfill as a no-op. The ledger is not changing; what it
        # is called here is, because this is the sentence a model reads back to a person.
        written = {
            "publication_id": publication_id,
            "rows_newly_stored": row["rows_written"],
            "rows_newly_stored_means": "rows the database accepted as new. A replay that rebuilt "
                                       "an entire table reports 0 here and says what it did in "
                                       "`verdict` — see the run's detail line, not this count.",
        }
    return Answer(
        question="run detail",
        found=True,
        detail={
            "run_id": row["id"],
            "source": row["source"],
            "outcome": row["outcome"],
            "outcome_meaning": {
                "stored": "the source published content the ingest had not held before",
                "no_change": "the source answered and republished nothing — a success, and the "
                             "ordinary outcome for the forecast (D42). **A rows-only replay also "
                             "records no_change**: the claim short-circuits on a hash already "
                             "held, so the rebuild is in `verdict` and not in any count",
                "failed": "the source did not answer usefully; this is not the same as no_change",
            }[row["outcome"]],
            "started_at": row["started_at"].isoformat(),
            "finished_at": row["finished_at"].isoformat(),
            "invoked_by": row["invoked_by"],
            "verdict": row["detail"],
            "wrote": written,
        },
        note=None,
    )


async def run_history(session, source: Optional[str] = None, limit: int = 20) -> Answer:
    from sqlalchemy import text

    if source is None:
        rows = (await session.execute(text(RUN_HISTORY_ALL), {"limit": limit})).mappings().all()
    else:
        rows = (
            await session.execute(
                text(RUN_HISTORY_FOR_SOURCE), {"source": source, "limit": limit}
            )
        ).mappings().all()
    return Answer(
        question="run history",
        found=bool(rows),
        detail={"source": source, "returned": len(rows)},
        rows=[
            {
                "run_id": row["id"],
                "source": row["source"],
                "outcome": row["outcome"],
                # Same rename as `run detail` above, same reason: a count of rows *newly
                # stored*, which a replay leaves at 0 however much it rewrote.
                "rows_newly_stored": row["rows_written"],
                "invoked_by": row["invoked_by"],
                "started_at": row["started_at"].isoformat(),
            }
            for row in rows
        ],
        note=None if rows else "no runs recorded yet",
    )


PUBLICATION_FORECAST = """
select p.id, p.dataset_id, p.content_sha256, p.detected_at, p.payload_bytes,
       (select count(*) from forecast_reading r where r.publication_id = p.id) as reading_rows,
       (select count(distinct r.township_code) from forecast_reading r where r.publication_id = p.id) as townships
from forecast_publication p where p.id = :publication_id
"""

PUBLICATION_OBSERVATION = """
select p.id, p.dataset_id, p.content_sha256, p.detected_at, p.payload_bytes,
       (select count(*) from observation_reading r where r.publication_id = p.id) as reading_rows,
       (select count(distinct r.station_id) from observation_reading r where r.publication_id = p.id) as stations
from observation_publication p where p.id = :publication_id
"""


async def publication_detail(session, dataset_id: str, publication_id: int) -> Answer:
    """What one publication holds. The counts are queried, never remembered."""
    from sqlalchemy import text

    statement = (
        PUBLICATION_FORECAST if dataset_id == FORECAST_DATASET else PUBLICATION_OBSERVATION
    )
    row = (
        await session.execute(text(statement), {"publication_id": publication_id})
    ).mappings().first()
    if row is None:
        return Answer(
            question="publication detail",
            found=False,
            detail={"dataset_id": dataset_id, "publication_id": publication_id},
            note="no publication with that id in that dataset",
        )
    label = _time_label(dataset_id)
    body = {
        "publication_id": row["id"],
        "dataset_id": row["dataset_id"],
        "content_sha256": row["content_sha256"],
        label: row["detected_at"].isoformat(),
        "payload_bytes": row["payload_bytes"],
        "reading_rows": row["reading_rows"],
    }
    body["townships" if dataset_id == FORECAST_DATASET else "stations"] = (
        row["townships"] if dataset_id == FORECAST_DATASET else row["stations"]
    )
    return Answer(question="publication detail", found=True, detail=body)


def refuse(subject: str) -> None:
    """H20's boundary, as a function so the refusal has one wording and one test.

    The tool answers over `contextual` and `commercial` in full and over `private` **only in
    aggregate** — that a private contribution applied and its numeric effect, never whose or
    why. None of that is reachable from here at all: the weight engine is unbuilt and this
    module reads no table that carries a member or a channel. Until it does, the honest answer
    to a question about one is a refusal that says why.
    """
    raise LineageRefused(
        "this tool answers lineage over ingested rows and cannot answer about {}. The private "
        "weight channel is answerable only in aggregate — that a contribution applied and its "
        "numeric effect, never whose or why (H20, D13) — and the weight engine is not built, so "
        "no such row exists to aggregate. Asking a person's reason out of a lineage tool is the "
        "leak this boundary exists to stop.".format(subject)
    )
