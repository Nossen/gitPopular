from __future__ import annotations

from datetime import UTC, date, datetime

from gitpopular.archive import count_watch_events, gharchive_hour_url, merge_growths, utc_hours_for_local_date
from gitpopular.models import StarGrowth


def test_count_watch_events_filters_started_stars_and_dedupes_actor_repo_pairs() -> None:
    events = [
        {
            "type": "WatchEvent",
            "payload": {"action": "started"},
            "repo": {"id": 1, "name": "owner/ai-one"},
            "actor": {"id": 10},
        },
        {
            "type": "WatchEvent",
            "payload": {"action": "started"},
            "repo": {"id": 1, "name": "owner/ai-one"},
            "actor": {"id": 10},
        },
        {
            "type": "WatchEvent",
            "payload": {"action": "started"},
            "repo": {"id": 1, "name": "owner/ai-one"},
            "actor": {"id": 11},
        },
        {
            "type": "WatchEvent",
            "payload": {"action": "deleted"},
            "repo": {"id": 1, "name": "owner/ai-one"},
            "actor": {"id": 12},
        },
        {
            "type": "ForkEvent",
            "payload": {},
            "repo": {"id": 2, "name": "owner/not-a-star"},
            "actor": {"id": 13},
        },
    ]

    growths = count_watch_events(events)

    assert growths == [
        StarGrowth(repo_id=1, repo_name="owner/ai-one", yesterday_new_stars=2, actor_ids=frozenset({10, 11}))
    ]


def test_utc_hours_for_beijing_report_day_maps_to_prior_utc_afternoon() -> None:
    hours = utc_hours_for_local_date(date(2026, 5, 25), "Asia/Shanghai")

    assert len(hours) == 24
    assert hours[0] == datetime(2026, 5, 24, 16, tzinfo=UTC)
    assert hours[-1] == datetime(2026, 5, 25, 15, tzinfo=UTC)


def test_gharchive_hour_url_uses_unpadded_hour() -> None:
    assert gharchive_hour_url(datetime(2026, 5, 24, 6, tzinfo=UTC)).endswith("/2026-05-24-6.json.gz")


def test_merge_growths_dedupes_across_hour_batches() -> None:
    merged = merge_growths(
        [
            [StarGrowth(1, "owner/repo", 2, frozenset({1, 2}))],
            [StarGrowth(1, "owner/repo", 2, frozenset({2, 3}))],
        ]
    )

    assert merged == [StarGrowth(1, "owner/repo", 3, frozenset({1, 2, 3}))]
