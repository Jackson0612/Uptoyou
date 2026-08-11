#!/usr/bin/env python3
"""Item 10's ingest, tested without a network or a database.

Run: python3 app/api/tests/test_cwa_ingest.py

Everything here is a pure function on a payload, which is why the parsing and the hashing
were separated from the fetching in the first place. The fixtures are trimmed real shapes,
not invented ones — the field names and the nesting are what CWA actually sends.
"""

import json
import os
import ssl
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from upto.ingest import cwa  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))


def forecast_payload(temperature="32", noise="anything"):
    return {
        "success": "true",
        # Envelope noise: present in real responses, different on every call, and must not
        # reach the hash — otherwise every hourly run looks like a new publication.
        "result": {"resource_id": noise, "fields": [{"id": noise}]},
        "records": {
            "Locations": [
                {
                    "LocationsName": "臺北市",
                    "Location": [
                        {
                            "LocationName": "中山區",
                            "WeatherElement": [
                                {
                                    "ElementName": "溫度",
                                    "Time": [
                                        {
                                            "DataTime": "2026-08-11T18:00:00+08:00",
                                            "ElementValue": [{"Temperature": temperature}],
                                        }
                                    ],
                                },
                                {
                                    "ElementName": "舒適度指數",
                                    "Time": [
                                        {
                                            "DataTime": "2026-08-11T18:00:00+08:00",
                                            "ElementValue": [
                                                {"ComfortIndex": "29", "ComfortIndexDescription": "悶熱"}
                                            ],
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    }


def observation_payload(temperature="30.5", weather="陰"):
    return {
        "success": "true",
        "records": {
            "Station": [
                {
                    "StationName": "臺北",
                    "StationId": "466920",
                    "ObsTime": {"DateTime": "2026-08-11T18:00:00+08:00"},
                    "GeoInfo": {"CountyName": "臺北市", "TownName": "中正區"},
                    "WeatherElement": {
                        "AirTemperature": temperature,
                        "Weather": weather,
                        "WindSpeed": "-99",
                        "Now": {"Precipitation": "2.0"},
                    },
                }
            ]
        },
    }


class ForecastParsing(unittest.TestCase):
    def test_element_and_measure_are_separate(self):
        rows = {(r.element, r.measure): r.value for r in cwa.parse_forecast(forecast_payload())}
        self.assertEqual(rows[("溫度", "Temperature")], "32")
        self.assertEqual(rows[("舒適度指數", "ComfortIndexDescription")], "悶熱")

    def test_one_element_carrying_two_measures_makes_two_rows(self):
        rows = [r for r in cwa.parse_forecast(forecast_payload()) if r.element == "舒適度指數"]
        self.assertEqual(len(rows), 2)

    def test_timestamps_carry_an_offset(self):
        for row in cwa.parse_forecast(forecast_payload()):
            self.assertIsNotNone(row.slot_start.tzinfo, "H17: a stamp without a zone is the hazard")

    def test_empty_payload_is_a_failure_not_an_empty_success(self):
        with self.assertRaises(cwa.CwaUnavailable):
            cwa.parse_forecast({"records": {"Locations": []}})


class ObservationParsing(unittest.TestCase):
    def test_reads_station_and_town(self):
        rows = {r.element: r for r in cwa.parse_observation(observation_payload())}
        self.assertEqual(rows["AirTemperature"].station_id, "466920")
        self.assertEqual(rows["AirTemperature"].town, "中正區")

    def test_sentinel_becomes_null_rather_than_a_number(self):
        """-99 means no reading. Stored as a number it would be averaged into nonsense."""
        rows = {r.element: r.value for r in cwa.parse_observation(observation_payload())}
        self.assertIsNone(rows["WindSpeed"])

    def test_absent_weather_text_is_recorded_as_absent(self):
        """The `Weather` field's absence is an open measurement question; a row keeps it answerable."""
        rows = {r.element: r.value for r in cwa.parse_observation(observation_payload(weather=""))}
        self.assertIn("Weather", rows)
        self.assertIsNone(rows["Weather"])

    def test_nested_value_is_kept_rather_than_dropped(self):
        rows = {r.element: r.value for r in cwa.parse_observation(observation_payload())}
        self.assertEqual(json.loads(rows["Now"]), {"Precipitation": "2.0"})


class ContentDigest(unittest.TestCase):
    def test_envelope_noise_does_not_change_the_hash(self):
        """This is the whole of D42: an hourly fetch of unchanged content must be a no-op."""
        first = cwa.content_digest(cwa.FORECAST_DATASET, forecast_payload(noise="call-1"))
        second = cwa.content_digest(cwa.FORECAST_DATASET, forecast_payload(noise="call-2"))
        self.assertEqual(first, second)

    def test_a_changed_reading_changes_the_hash(self):
        first = cwa.content_digest(cwa.FORECAST_DATASET, forecast_payload(temperature="32"))
        second = cwa.content_digest(cwa.FORECAST_DATASET, forecast_payload(temperature="33"))
        self.assertNotEqual(first, second)

    def test_observation_hash_behaves_the_same_way(self):
        same = cwa.content_digest(cwa.OBSERVATION_DATASET, observation_payload())
        again = cwa.content_digest(cwa.OBSERVATION_DATASET, observation_payload())
        changed = cwa.content_digest(cwa.OBSERVATION_DATASET, observation_payload(temperature="31.0"))
        self.assertEqual(same, again)
        self.assertNotEqual(same, changed)

    def test_hash_is_sha256_shaped(self):
        digest = cwa.content_digest(cwa.OBSERVATION_DATASET, observation_payload())
        self.assertEqual(len(digest), 64)


class TlsPosture(unittest.TestCase):
    """The fix for CWA's chain must not become a fix that trusts anybody."""

    def test_certificates_are_still_verified(self):
        context = cwa.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_only_the_strict_flag_is_relaxed(self):
        context = cwa.tls_context()
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_STRICT)


class KeyNeverLeaks(unittest.TestCase):
    def test_a_failed_fetch_does_not_repeat_the_url(self):
        """The URL carries the key as a query parameter, so it may never reach a message."""
        key = "CWA-" + "0123ABCD-4567-89EF-0123-456789ABCDEF"

        def explode(url):
            raise OSError("connection refused to " + url)

        with self.assertRaises(cwa.CwaUnavailable) as caught:
            cwa._fetch_json(cwa.FORECAST_DATASET, key, opener=explode)
        message = str(caught.exception)
        self.assertNotIn(key, message)
        self.assertNotIn("Authorization", message)

    def test_a_rejected_key_is_reported_without_the_key(self):
        with self.assertRaises(cwa.CwaUnavailable) as caught:
            cwa._fetch_json(cwa.FORECAST_DATASET, "some-key", opener=lambda url: b'{"success":"false"}')
        self.assertNotIn("some-key", str(caught.exception))


class FetchAssembly(unittest.TestCase):
    def test_publication_carries_hash_size_and_detection_time(self):
        raw = json.dumps(observation_payload()).encode("utf-8")
        fixed = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
        publication = cwa.fetch_publication(
            cwa.OBSERVATION_DATASET, "k", now=lambda: fixed, opener=lambda url: raw
        )
        self.assertEqual(publication.detected_at, fixed)
        self.assertEqual(publication.payload_bytes, len(raw))
        self.assertEqual(len(publication.content_sha256), 64)
        self.assertTrue(publication.observation_rows)
        self.assertFalse(publication.forecast_rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
