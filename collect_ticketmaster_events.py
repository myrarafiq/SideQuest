#!/usr/bin/env python3
"""Collect a sample of upcoming New York Ticketmaster events.

The Discovery API supplies dated events, venues, booking links, and price
ranges when Ticketmaster has them. A price range does not mean tickets remain.
A missing price is unknown, not free.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ID = "ticketmaster-discovery-v2"
SOURCE_NAME = "Ticketmaster Discovery API"
ENDPOINT = "https://app.ticketmaster.com/discovery/v2/events.json"
TIMEZONE_NAME = "America/New_York"
NYC = ZoneInfo(TIMEZONE_NAME)
PAGE_SIZE = 40
WINDOW_DAYS = 14
SEARCHES = (
    {"city": "New York", "classificationName": "music"},
    {"city": "New York", "classificationName": "sports"},
    {"city": "New York", "classificationName": "arts & theatre"},
    {"city": "Brooklyn", "classificationName": "music"},
    {"city": "Brooklyn", "classificationName": "sports"},
    {"city": "Brooklyn", "classificationName": "arts & theatre"},
)
REQUEST_TIMEOUT_SECONDS = 40
OUTPUT_ROOT = Path(__file__).resolve().parent / "data" / "ticketmaster"
ENV_PATH = Path(__file__).resolve().parent / ".env"

CSV_FIELDS = (
    "source_id",
    "event_id",
    "title",
    "segment",
    "genre",
    "venue_name",
    "venue_city",
    "venue_state",
    "address",
    "postal_code",
    "latitude",
    "longitude",
    "start_date",
    "start_time",
    "starttime",
    "timezone",
    "date_tbd",
    "time_tbd",
    "event_status",
    "price_currency",
    "price_min",
    "price_max",
    "price_range_count",
    "ticket_url",
    "collected_at",
)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.environ.get("TICKETMASTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Missing TICKETMASTER_API_KEY. Add it to .env in the project root. Nothing was written."
        )
    return key


def redact(text: str, key: str) -> str:
    return text.replace(key, "[redacted]")


def request_json(url: str, key: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "SideQuest-collection/0.1"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as error:
            detail = redact(error.read().decode("utf-8", "replace"), key)
            if error.code in {429, 500, 503} and attempt < 2:
                last_error = RuntimeError(f"HTTP {error.code}: {detail[:500]}")
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"Ticketmaster request failed with HTTP {error.code}: {detail[:800]}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = RuntimeError(redact(str(error), key))
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"Ticketmaster request failed: {last_error}") from error
    else:
        raise RuntimeError(f"Ticketmaster request failed: {last_error}")
    if not isinstance(payload, dict):
        raise RuntimeError("Ticketmaster returned a response that was not an object")
    return payload


def fetch_events(key: str, start: datetime, end: datetime, search: dict) -> list[dict]:
    params = {
        "apikey": key,
        "stateCode": "NY",
        "countryCode": "US",
        "startDateTime": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sort": "date,asc",
        "size": PAGE_SIZE,
        "page": 0,
        **search,
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    payload = request_json(url, key)
    embedded = payload.get("_embedded") if isinstance(payload.get("_embedded"), dict) else {}
    events = embedded.get("events") or []
    if not isinstance(events, list):
        raise RuntimeError("Ticketmaster response did not include an events list")
    return events


def text_of(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def number_of(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def primary_classification(raw: dict) -> tuple[str | None, str | None]:
    classifications = raw.get("classifications")
    if not isinstance(classifications, list):
        return None, None
    chosen = next((item for item in classifications if isinstance(item, dict) and item.get("primary")), None)
    if chosen is None:
        chosen = next((item for item in classifications if isinstance(item, dict)), None)
    if not isinstance(chosen, dict):
        return None, None
    segment = chosen.get("segment") if isinstance(chosen.get("segment"), dict) else {}
    genre = chosen.get("genre") if isinstance(chosen.get("genre"), dict) else {}
    return text_of(segment.get("name")), text_of(genre.get("name"))


def price_facts(raw: dict) -> dict:
    ranges = raw.get("priceRanges")
    if not isinstance(ranges, list):
        ranges = []
    usable = [item for item in ranges if isinstance(item, dict)]
    usd = [item for item in usable if item.get("currency") == "USD"] or usable
    mins = [amount for amount in (number_of(item.get("min")) for item in usd) if amount is not None]
    maxes = [amount for amount in (number_of(item.get("max")) for item in usd) if amount is not None]
    if mins and maxes and max(mins) == 0 and max(maxes) == 0:
        mins = []
        maxes = []
    currency = text_of(usd[0].get("currency")) if usd else None
    return {
        "price_currency": currency,
        "price_min": min(mins) if mins else None,
        "price_max": max(maxes) if maxes else None,
        "price_range_count": len(usable),
    }


def local_start(raw: dict) -> dict:
    dates = raw.get("dates") if isinstance(raw.get("dates"), dict) else {}
    start = dates.get("start") if isinstance(dates.get("start"), dict) else {}
    status = dates.get("status") if isinstance(dates.get("status"), dict) else {}
    timezone_name = text_of(dates.get("timezone")) or TIMEZONE_NAME
    local_date = text_of(start.get("localDate"))
    local_time = text_of(start.get("localTime"))
    date_tbd = bool(start.get("dateTBD")) or local_date is None
    time_tbd = bool(start.get("timeTBD")) or local_time is None
    starttime = None
    if local_date and local_time and not date_tbd and not time_tbd:
        try:
            parsed = datetime.strptime(f"{local_date} {local_time}", "%Y-%m-%d %H:%M:%S")
            starttime = parsed.replace(tzinfo=ZoneInfo(timezone_name)).isoformat()
        except (ValueError, KeyError):
            starttime = None
    return {
        "start_date": None if date_tbd else local_date,
        "start_time": None if time_tbd else local_time,
        "starttime": starttime,
        "timezone": timezone_name,
        "date_tbd": date_tbd,
        "time_tbd": time_tbd,
        "event_status": text_of(status.get("code")),
    }


def venue_facts(raw: dict) -> dict:
    embedded = raw.get("_embedded") if isinstance(raw.get("_embedded"), dict) else {}
    venues = embedded.get("venues") if isinstance(embedded.get("venues"), list) else []
    venue = next((item for item in venues if isinstance(item, dict)), {})
    city = venue.get("city") if isinstance(venue.get("city"), dict) else {}
    state = venue.get("state") if isinstance(venue.get("state"), dict) else {}
    address = venue.get("address") if isinstance(venue.get("address"), dict) else {}
    location = venue.get("location") if isinstance(venue.get("location"), dict) else {}
    return {
        "venue_name": text_of(venue.get("name")),
        "venue_city": text_of(city.get("name")),
        "venue_state": text_of(state.get("stateCode")),
        "address": text_of(address.get("line1")),
        "postal_code": text_of(venue.get("postalCode")),
        "latitude": number_of(location.get("latitude")),
        "longitude": number_of(location.get("longitude")),
    }


def normalize_event(raw: dict, collected_at: str) -> dict:
    return {
        "source_id": SOURCE_ID,
        "event_id": text_of(raw.get("id")),
        "title": text_of(raw.get("name")),
        "segment": primary_classification(raw)[0],
        "genre": primary_classification(raw)[1],
        **venue_facts(raw),
        **local_start(raw),
        **price_facts(raw),
        "ticket_url": text_of(raw.get("url")),
        "collected_at": collected_at,
    }


def load_previous_ids(snapshots_dir: Path) -> tuple[str | None, set[str]]:
    if not snapshots_dir.is_dir():
        return None, set()
    candidates = [path / "events.json" for path in snapshots_dir.iterdir() if (path / "events.json").is_file()]
    if not candidates:
        return None, set()
    previous_file = max(candidates, key=lambda path: path.stat().st_mtime)
    previous_events = json.loads(previous_file.read_text(encoding="utf-8"))
    ids = {str(event.get("event_id")) for event in previous_events if event.get("event_id")}
    return previous_file.parent.name, ids


def csv_row(event: dict) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in CSV_FIELDS:
        value = event.get(field)
        if isinstance(value, bool):
            row[field] = "true" if value else "false"
        elif value is None:
            row[field] = ""
        else:
            row[field] = str(value)
    return row


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for event in events:
            writer.writerow(csv_row(event))


def missing_counts(events: list[dict]) -> dict[str, int]:
    fields = (
        "event_id",
        "title",
        "starttime",
        "venue_name",
        "venue_city",
        "latitude",
        "longitude",
        "price_min",
        "price_max",
        "ticket_url",
        "segment",
    )
    counts = {field: 0 for field in fields}
    for event in events:
        for field in fields:
            value = event.get(field)
            if value is None or value == "":
                counts[field] += 1
    return counts


def main() -> int:
    key = api_key()
    now = datetime.now(NYC)
    collected_at = now.isoformat()
    window_end = now + timedelta(days=WINDOW_DAYS)
    window_start_date = now.date()
    window_end_date = window_end.date()
    raw_events: list[dict] = []
    for search in SEARCHES:
        raw_events.extend(fetch_events(key, now, window_end, search))
    if not raw_events:
        raise RuntimeError("Ticketmaster returned no events. Nothing was written.")

    events = []
    seen: set[str] = set()
    for raw in raw_events:
        event = normalize_event(raw, collected_at)
        event_id = event.get("event_id")
        title = (event.get("title") or "").lower()
        if not event_id or event_id in seen:
            continue
        if event.get("venue_state") not in {None, "NY"}:
            continue
        if "not a concert ticket" in title or "add on" in title or "add-on" in title:
            continue
        start_date = event.get("start_date")
        if start_date is None:
            continue
        try:
            event_day = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if event_day < window_start_date or event_day > window_end_date:
            continue
        seen.add(event_id)
        events.append(event)
    if not events:
        raise RuntimeError("Ticketmaster returned no New York events. Nothing was written.")

    previous_snapshot, previous_ids = load_previous_ids(OUTPUT_ROOT / "snapshots")
    is_baseline = previous_snapshot is None
    new_events = [] if is_baseline else [event for event in events if event["event_id"] not in previous_ids]
    priced = sum(1 for event in events if event.get("price_min") is not None or event.get("price_max") is not None)
    manifest = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "endpoint": ENDPOINT,
        "collected_at": collected_at,
        "timezone": TIMEZONE_NAME,
        "filters": {
            "state_code": "NY",
            "cities": ["New York", "Brooklyn"],
            "classifications": ["music", "sports", "arts & theatre"],
            "window_days": WINDOW_DAYS,
            "sort": "date,asc",
            "page_size_per_search": PAGE_SIZE,
        },
        "row_count": len(events),
        "priced_count": priced,
        "missing_field_counts": missing_counts(events),
        "notes": [
            "Blank CSV cells are null.",
            "Sample of music, sports, and arts events in New York and Brooklyn over the next 14 days, not the full catalog.",
            "price_min and price_max are Ticketmaster's supplied range. They do not mean tickets remain for a group.",
            "A missing price is unknown, not free. A 0 to 0 range from Ticketmaster is stored as missing.",
            "starttime is the local start in the event timezone. A TBD date or time stays null.",
            "venue_city is the venue's city name. New York is not recorded as a verified borough.",
            "event_status such as onsale is Ticketmaster's sale status, not confirmed group inventory.",
            (
                "This run is the first snapshot, so no event is marked new today."
                if is_baseline
                else "new_since_last_run.json lists event ids that were absent from the previous snapshot."
            ),
        ],
    }
    new_since = {
        "collected_at": collected_at,
        "compared_to_snapshot": previous_snapshot,
        "is_baseline": is_baseline,
        "current_event_count": len(events),
        "new_event_count": len(new_events),
        "note": (
            "First collection establishes a baseline. These rows are not marked as new today."
            if is_baseline
            else f"Compared with snapshot {previous_snapshot}."
        ),
        "new_events": new_events,
    }

    latest_dir = OUTPUT_ROOT / "latest"
    snapshot_dir = OUTPUT_ROOT / "snapshots" / now.date().isoformat()
    for directory in (latest_dir, snapshot_dir):
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory / "events.json", events)
        write_csv(directory / "events.csv", events)
        write_json(directory / "manifest.json", manifest)
        write_json(directory / "new_since_last_run.json", new_since)

    print(f"Collected {len(events)} Ticketmaster events at {collected_at}")
    print(f"Events with a price range: {priced} of {len(events)}")
    print(f"Wrote {latest_dir}")
    if is_baseline:
        print("Baseline run: no events marked as new today.")
    else:
        print(f"New since snapshot {previous_snapshot}: {len(new_events)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        raise SystemExit(1)
