from __future__ import annotations

import gzip
import json
import time as time_module
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO, TextIOWrapper
from typing import Iterable, Mapping, Any
from zoneinfo import ZoneInfo

import httpx

from .models import StarGrowth


GHARCHIVE_BASE_URL = "https://data.gharchive.org"


def parse_report_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def utc_hours_for_local_date(report_date: date, timezone_name: str) -> list[datetime]:
    tz = ZoneInfo(timezone_name)
    local_start = datetime.combine(report_date, time.min, tzinfo=tz)
    hours: list[datetime] = []
    for offset in range(24):
        local_hour = local_start + timedelta(hours=offset)
        utc_hour = local_hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        hours.append(utc_hour)
    return hours


def gharchive_hour_url(hour: datetime) -> str:
    hour = hour.astimezone(UTC)
    return f"{GHARCHIVE_BASE_URL}/{hour:%Y-%m-%d}-{hour.hour}.json.gz"


def count_watch_events(events: Iterable[Mapping[str, Any]]) -> list[StarGrowth]:
    repo_actors: dict[int, set[int]] = defaultdict(set)
    repo_names: dict[int, str] = {}

    for event in events:
        if event.get("type") != "WatchEvent":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("action") != "started":
            continue
        repo = event.get("repo")
        actor = event.get("actor")
        if not isinstance(repo, Mapping) or not isinstance(actor, Mapping):
            continue
        repo_id = _as_int(repo.get("id"))
        actor_id = _as_int(actor.get("id"))
        repo_name = repo.get("name")
        if repo_id is None or actor_id is None or not isinstance(repo_name, str):
            continue

        repo_actors[repo_id].add(actor_id)
        repo_names[repo_id] = repo_name

    return _growths_from_actor_map(repo_actors, repo_names)


def parse_watch_events(lines: Iterable[str]) -> list[StarGrowth]:
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return count_watch_events(events)


def parse_watch_events_gzip(payload: bytes) -> list[StarGrowth]:
    with gzip.GzipFile(fileobj=BytesIO(payload)) as gz:
        with TextIOWrapper(gz, encoding="utf-8") as text:
            return parse_watch_events(text)


def merge_growths(growth_batches: Iterable[Iterable[StarGrowth]]) -> list[StarGrowth]:
    repo_actors: dict[int, set[int]] = defaultdict(set)
    repo_names: dict[int, str] = {}

    for batch in growth_batches:
        for growth in batch:
            repo_actors[growth.repo_id].update(growth.actor_ids)
            repo_names[growth.repo_id] = growth.repo_name

    return _growths_from_actor_map(repo_actors, repo_names)


class GHArchiveClient:
    def __init__(self, client: httpx.Client | None = None, retries: int = 3) -> None:
        self.client = client or httpx.Client(timeout=httpx.Timeout(90.0), follow_redirects=True)
        self.retries = retries

    def fetch_hour(self, hour: datetime) -> list[StarGrowth]:
        url = gharchive_hour_url(hour)
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return parse_watch_events_gzip(response.content)
            except httpx.HTTPStatusError:
                raise
            except (httpx.HTTPError, OSError, EOFError, gzip.BadGzipFile) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time_module.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(f"Failed to fetch or parse GH Archive hour {url}") from last_error

    def fetch_daily_growth(self, report_date: date, timezone_name: str) -> list[StarGrowth]:
        batches = []
        for hour in utc_hours_for_local_date(report_date, timezone_name):
            batches.append(self.fetch_hour(hour))
        return merge_growths(batches)


def _growths_from_actor_map(
    repo_actors: Mapping[int, set[int]],
    repo_names: Mapping[int, str],
) -> list[StarGrowth]:
    growths = [
        StarGrowth(
            repo_id=repo_id,
            repo_name=repo_names[repo_id],
            yesterday_new_stars=len(actor_ids),
            actor_ids=frozenset(actor_ids),
        )
        for repo_id, actor_ids in repo_actors.items()
    ]
    return sorted(growths, key=lambda item: (-item.yesterday_new_stars, item.repo_name.lower()))


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
