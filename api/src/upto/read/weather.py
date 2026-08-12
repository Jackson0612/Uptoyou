"""Ticket 07 — one call over two tables, and it says which one answered.

Given a township code and a target hour, return the weather for that hour: **the observation
if it exists, otherwise the forecast for that same hour** (D36). Two tables, one read path
(D23), and the caller never chooses between them.

**The fallback window falls out of the design rather than being coded.** The observation for
an hour lands about ten minutes into it — measured at 8.7 and 10.1 minutes, spread 1.3. Ask
before it lands and the exact-hour query finds nothing, so the forecast for that same hour
answers. Nothing here compares clocks or subtracts offsets, which is the point: **the
previous hour's observation is never a candidate**, because the query matches the described
hour exactly. That is H15 closed structurally rather than by care — a reading older than the
hour it claims to describe cannot be selected at all.

**Every answer names the row it came from**, because D15's snapshot has to pin what a round
actually read, and item 14 has to be able to answer for it later. A forecast's timestamp is
returned labelled a **detection** time (D42): CWA never says when a forecast was published,
so nothing downstream may present it as publication.

**One thing here is assumed rather than ruled, and it is flagged in `_map.md`.** The
observation is revised *in place* within its own hour — measured 2026-08-11, two publications
carrying the same `ObsTime` and eight differing rows of 7,884. So "the observation for that
hour" now has more than one version, and this module takes **the latest publication for that
hour**. It is reversible: every version is stored, the answer names the publication it used,
and a round that pinned an earlier one still reads as it did. The ruling is owed; the data is
not at risk either way.

**Both tables are now reached by identifier, which closes ticket 05's gap.** The forecast used
to be found by township *name*, and the guard below existed because a misspelling and an
absence are indistinguishable — 台 against 臺 is H24 exactly. CWA's payload carries `Geocode`
beside the name in the same code space the seed uses, so revision 0003 keys the forecast on
the code and the name is only quoted back. The guard survives in a narrower form: no forecast
row for this code *at all* means the ingest has not run or the code space moved, and neither
is an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text

# Normalised names, so a caller does not have to know which table answered. The mapping is
# stated rather than guessed: these are the element/measure pairs the two datasets actually
# carry, read off the ingested rows.
OBSERVATION_MEASURES = {
    "temperature_c": ("AirTemperature", None),
    "humidity_pct": ("RelativeHumidity", None),
    "weather_text": ("Weather", None),
    "wind_speed_ms": ("WindSpeed", None),
}
FORECAST_MEASURES = {
    "temperature_c": ("溫度", "Temperature"),
    "humidity_pct": ("相對濕度", "RelativeHumidity"),
    "weather_text": ("天氣現象", "Weather"),
    "wind_speed_ms": ("風速", "WindSpeed"),
    "rain_probability_pct": ("3小時降雨機率", "ProbabilityOfPrecipitation"),
    "apparent_temperature_c": ("體感溫度", "ApparentTemperature"),
    "comfort_text": ("舒適度指數", "ComfortIndexDescription"),
}


class TownshipUnknown(LookupError):
    """No seeded mapping. D32's loader refuses to leave one missing, so this means the
    township code is not a 臺北市 one rather than that the seed is incomplete."""


class ForecastJoinBroken(RuntimeError):
    """No forecast row carries this township code, for any hour.

    Raised rather than reported as an absence, because an absence here would be
    indistinguishable from "no forecast published for that hour". Since revision 0003 the join
    is on the geocode, so this can no longer mean a misspelling (H24) — it means the ingest has
    not run, or CWA changed the code space.
    """


@dataclass(frozen=True)
class Provenance:
    publication_id: int
    dataset_id: str
    content_sha256: str
    # For the forecast this is a *detection* time, never a publication time (D42). The field
    # is named for what it is and `time_label` says which, so a caller cannot get it wrong by
    # reading the name alone.
    detected_at: datetime
    time_label: str


@dataclass(frozen=True)
class WeatherReading:
    kind: str                      # "observation" | "forecast" | "absent"
    township_code: str
    township_name: str
    hour: datetime                 # the hour described, always the one asked for
    measures: dict = field(default_factory=dict)
    # Which slot each measure was taken from, as `label -> (start, end)`, `end` being None for
    # the last slot in a series. **This exists because of the 2026-08-12 ruling** that a value
    # is read from the slot containing the hour: once 10:00's 天氣 can come from the 09:00–12:00
    # block, "the forecast for 10:00" is no longer self-describing, and D15's snapshot has to
    # be able to pin what a round actually read. Empty for an observation, whose ObsTime is
    # the hour itself.
    slots: dict = field(default_factory=dict)
    station_id: str | None = None
    station_name: str | None = None
    provenance: Provenance | None = None
    absence_reason: str | None = None

    @property
    def present(self) -> bool:
        return self.kind != "absent"

    def line(self) -> str:
        if not self.present:
            return "{} {}: no reading — {}".format(
                self.township_name, self.hour.isoformat(), self.absence_reason
            )
        return "{} {}: {} from publication {} ({})".format(
            self.township_name,
            self.hour.isoformat(),
            self.kind,
            self.provenance.publication_id,
            self.provenance.time_label,
        )


TOWNSHIP = """
select township_code, township_name, station_id, station_name, resolution
from township_station where township_code = :code
"""

# The latest publication carrying this station and hour. `order by detected_at desc` is the
# assumption named in this module's docstring: the observation is revised in place, and the
# most recent version of an hour is taken. Every earlier one remains stored.
OBSERVATION = """
select r.element, r.value, p.id as publication_id, p.dataset_id, p.content_sha256, p.detected_at
from observation_reading r
join observation_publication p on p.id = r.publication_id
where r.station_id = :station_id and r.observed_at = :hour
  and p.id = (
      select p2.id from observation_reading r2
      join observation_publication p2 on p2.id = r2.publication_id
      where r2.station_id = :station_id and r2.observed_at = :hour
      order by p2.detected_at desc, p2.id desc limit 1
  )
"""

# **The slot that CONTAINS the hour, ruled 2026-08-12 — not the slot that starts on it.**
#
# This read `slot_start = :hour` until then, and one hour in three looked complete while the
# other two showed nothing for half the card. Measured, on publication 27 for 中山區:
#
#   Temperature, ApparentTemperature, RelativeHumidity …  56 slots, `slot_end` always NULL,
#       spaced 1 hour for the first 36 gaps and **3 hours for the remaining 19**
#   Weather, ProbabilityOfPrecipitation, WindSpeed …       32 slots, `slot_end` always set,
#       every gap 3 hours — 09:00–12:00 and so on
#
# So CWA publishes a value covering 10:00; it just does not start one there. Returning nothing
# for that hour told the caller the source was silent when it was not, and it is H23's
# *degrades quietly* shape: no error, no absence_reason, just half a screen of dashes.
#
# **`coalesce(slot_end, slot_start + interval '1 hour')` is the obvious fix and it is wrong.**
# Those 19 far-out Temperature slots span three hours and still carry a NULL `slot_end`, so a
# one-hour assumption drops two hours in three at the far end of the horizon — the same bug
# moved rather than fixed. The extent has to come from **the next slot in the same series**,
# which is what the window function below is for.
#
# A slot with no successor and no `slot_end` is the last one in its series; it covers its own
# start and nothing after, because extending it would invent a horizon the source never gave.
FORECAST = """
with slot as (
    select r.publication_id, r.element, r.measure, r.value, r.slot_start,
           coalesce(
               r.slot_end,
               lead(r.slot_start) over (
                   partition by r.publication_id, r.element, r.measure
                   order by r.slot_start
               )
           ) as slot_end
    from forecast_reading r
    where r.township_code = :code
),
covering as (
    select * from slot
    where slot_start <= :hour
      and case when slot_end is null then slot_start = :hour else :hour < slot_end end
)
select c.element, c.measure, c.value, c.slot_start, c.slot_end,
       p.id as publication_id, p.dataset_id, p.content_sha256, p.detected_at
from covering c
join forecast_publication p on p.id = c.publication_id
where p.id = (
    -- The newest publication that covers this hour, not simply the newest publication: a
    -- past hour is carried only by the older publications whose horizon still reached it.
    select p2.id from covering c2
    join forecast_publication p2 on p2.id = c2.publication_id
    order by p2.detected_at desc, p2.id desc limit 1
)
"""

FORECAST_CODE_EXISTS = "select 1 from forecast_reading where township_code = :code limit 1"


async def reading_for(session, township_code: str, hour: datetime) -> WeatherReading:
    """The one call. Observation for that hour, else forecast for that same hour, else absence."""
    found = await session.execute(text(TOWNSHIP), {"code": township_code})
    township = found.mappings().first()
    if township is None:
        raise TownshipUnknown(
            "no seeded mapping for township code {}. The seed refuses to load with one "
            "missing, so this is not a 臺北市 township.".format(township_code)
        )

    rows = (
        await session.execute(
            text(OBSERVATION), {"station_id": township["station_id"], "hour": hour}
        )
    ).mappings().all()
    if rows:
        values = {}
        for name, (element, _) in OBSERVATION_MEASURES.items():
            match = next((r for r in rows if r["element"] == element), None)
            if match is not None:
                values[name] = match["value"]
        first = rows[0]
        return WeatherReading(
            kind="observation",
            township_code=township["township_code"],
            township_name=township["township_name"],
            hour=hour,
            measures=values,
            station_id=township["station_id"],
            station_name=township["station_name"],
            provenance=Provenance(
                publication_id=first["publication_id"],
                dataset_id=first["dataset_id"],
                content_sha256=first["content_sha256"],
                detected_at=first["detected_at"],
                # An observation carries its own ObsTime, so the hour is the source's claim
                # and this stamp is only when we fetched it.
                time_label="retrieved",
            ),
        )

    name = township["township_name"]
    rows = (
        await session.execute(text(FORECAST), {"code": township_code, "hour": hour})
    ).mappings().all()
    if not rows:
        any_row = await session.execute(text(FORECAST_CODE_EXISTS), {"code": township_code})
        if any_row.first() is None:
            raise ForecastJoinBroken(
                "no forecast row carries township code {} for any hour. A code cannot be "
                "misspelled, so this is the ingest not having run or the code space having "
                "moved — neither of which is an absence.".format(township_code)
            )
        return WeatherReading(
            kind="absent",
            township_code=township["township_code"],
            township_name=name,
            hour=hour,
            absence_reason=(
                "no observation for that hour and no forecast slot covering it — the "
                "forecast reaches about three days ahead, and nothing older is kept for "
                "an hour once it has passed"
            ),
        )

    values = {}
    spans = {}
    for label, (element, measure) in FORECAST_MEASURES.items():
        match = next(
            (r for r in rows if r["element"] == element and r["measure"] == measure), None
        )
        if match is not None:
            values[label] = match["value"]
            spans[label] = (match["slot_start"], match["slot_end"])
    first = rows[0]
    return WeatherReading(
        kind="forecast",
        township_code=township["township_code"],
        township_name=name,
        hour=hour,
        measures=values,
        slots=spans,
        provenance=Provenance(
            publication_id=first["publication_id"],
            dataset_id=first["dataset_id"],
            content_sha256=first["content_sha256"],
            detected_at=first["detected_at"],
            # D42: CWA never says when a forecast was published, so this is when we first saw
            # it and must be described that way wherever it is shown.
            time_label="detected",
        ),
    )
