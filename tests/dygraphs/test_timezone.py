"""Timezone-correctness tests for overlay date serialization.

Annotations, shadings, events, and ``dateWindow`` all emit
``"YYYY-MM-DDTHH:MM:SS.000Z"`` strings — the ``Z`` suffix marks UTC.
So tz-aware non-UTC inputs must be *converted* to UTC before
formatting, not merely stamped with a ``Z`` on the local wall-clock
time. Without the conversion, a browser reading the resulting string
interprets the local time as UTC and shifts the value by the local
offset (e.g. 2 hours off for Europe/Zurich in summer).

These tests pin the fix at :func:`dygraphs.utils.ts_to_utc_iso` and
at every callsite in :mod:`dygraphs.dygraph`.
"""

from __future__ import annotations

import pandas as pd

from dygraphs import Dygraph
from dygraphs.utils import ts_to_utc_iso


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": [1, 2, 3, 4, 5]},
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )


class TestTsToUtcIsoHelper:
    """Contract for the shared UTC-ISO helper."""

    def test_naive_timestamp_assumed_utc(self) -> None:
        assert ts_to_utc_iso("2024-01-10 12:00:00") == "2024-01-10T12:00:00.000Z"

    def test_utc_timestamp_passes_through(self) -> None:
        t = pd.Timestamp("2024-01-10 12:00:00", tz="UTC")
        assert ts_to_utc_iso(t) == "2024-01-10T12:00:00.000Z"

    def test_tz_aware_converted_to_utc(self) -> None:
        """Zurich 12:00 in winter (UTC+1) is 11:00 UTC.

        The old ``strftime("%Y-%m-%dT%H:%M:%S.000Z")`` emitted
        ``"2024-01-10T12:00:00.000Z"`` — a 1-hour lie. The helper
        must emit the UTC equivalent.
        """
        t = pd.Timestamp("2024-01-10 12:00:00", tz="Europe/Zurich")
        assert ts_to_utc_iso(t) == "2024-01-10T11:00:00.000Z"

    def test_tz_aware_summer_dst_converted(self) -> None:
        """Zurich 12:00 in summer (UTC+2) is 10:00 UTC — DST respected."""
        t = pd.Timestamp("2024-07-10 12:00:00", tz="Europe/Zurich")
        assert ts_to_utc_iso(t) == "2024-07-10T10:00:00.000Z"

    def test_eastern_timezone_converted(self) -> None:
        """US/Eastern 12:00 winter (UTC-5) is 17:00 UTC."""
        t = pd.Timestamp("2024-01-10 12:00:00", tz="US/Eastern")
        assert ts_to_utc_iso(t) == "2024-01-10T17:00:00.000Z"

    def test_accepts_datetime_objects(self) -> None:
        from datetime import datetime, timezone

        t = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        assert ts_to_utc_iso(t) == "2024-01-10T12:00:00.000Z"


class TestAnnotationTimezone:
    """``.annotation(x=...)`` must convert tz-aware x to UTC."""

    def test_naive_x_stays_as_is(self) -> None:
        cfg = Dygraph(_df()).annotation("2024-01-03 12:00:00", "A").to_dict()
        assert cfg["annotations"][0]["x"] == "2024-01-03T12:00:00.000Z"

    def test_tz_aware_x_converted_to_utc(self) -> None:
        x = pd.Timestamp("2024-01-03 12:00:00", tz="Europe/Zurich")
        cfg = Dygraph(_df()).annotation(x, "A").to_dict()
        # 12:00 Zurich winter = 11:00 UTC
        assert cfg["annotations"][0]["x"] == "2024-01-03T11:00:00.000Z"


class TestShadingTimezone:
    """``.shading(from_=, to=)`` must convert tz-aware bounds to UTC."""

    def test_naive_bounds_stay_as_is(self) -> None:
        cfg = Dygraph(_df()).shading("2024-01-02 00:00", "2024-01-04 00:00").to_dict()
        assert cfg["shadings"][0]["from"] == "2024-01-02T00:00:00.000Z"
        assert cfg["shadings"][0]["to"] == "2024-01-04T00:00:00.000Z"

    def test_tz_aware_bounds_converted(self) -> None:
        f = pd.Timestamp("2024-01-02 00:00", tz="Europe/Zurich")
        t = pd.Timestamp("2024-01-04 00:00", tz="Europe/Zurich")
        cfg = Dygraph(_df()).shading(f, t).to_dict()
        # 00:00 Zurich winter = 23:00 UTC the previous day
        assert cfg["shadings"][0]["from"] == "2024-01-01T23:00:00.000Z"
        assert cfg["shadings"][0]["to"] == "2024-01-03T23:00:00.000Z"


class TestEventTimezone:
    """``.event(x=...)`` must convert tz-aware x to UTC."""

    def test_tz_aware_event_converted(self) -> None:
        x = pd.Timestamp("2024-01-03 12:00", tz="US/Eastern")  # UTC-5 winter
        cfg = Dygraph(_df()).event(x, "E").to_dict()
        assert cfg["events"][0]["pos"] == "2024-01-03T17:00:00.000Z"


class TestDateWindowTimezone:
    """``.range_selector(date_window=(start, end))`` must convert bounds to UTC."""

    def test_naive_date_window(self) -> None:
        cfg = (
            Dygraph(_df())
            .range_selector(date_window=("2024-01-02", "2024-01-04"))
            .to_dict()
        )
        assert cfg["attrs"]["dateWindow"] == [
            "2024-01-02T00:00:00.000Z",
            "2024-01-04T00:00:00.000Z",
        ]

    def test_tz_aware_date_window_converted(self) -> None:
        f = pd.Timestamp("2024-01-02 00:00", tz="Europe/Zurich")
        t = pd.Timestamp("2024-01-04 00:00", tz="Europe/Zurich")
        cfg = Dygraph(_df()).range_selector(date_window=(f, t)).to_dict()
        assert cfg["attrs"]["dateWindow"] == [
            "2024-01-01T23:00:00.000Z",
            "2024-01-03T23:00:00.000Z",
        ]
