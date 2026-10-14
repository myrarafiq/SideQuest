#!/usr/bin/env python3
"""Collect NYC Parks upcoming public events and record what is new since the last pull.

The source is the public SODA API for dataset w3wp-dpdi, a rolling window of
events on NYC Parks properties over the next 14 days. The feed has no
date-added field, so an event is new only when its guid was absent from the
previous snapshot. The first run stores the current window as a baseline.
"""

from __future__ import annotations

import csv
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ID = "w3wp-dpdi"
SOURCE_NAME = "NYC Parks Public Events: Upcoming 14 Days"
ENDPOINT = "https://data.cityofnewyork.us/resource/w3wp-dpdi.json"
DATASET_URL = (
    "https://data.cityofnewyork.us/City-Government/"
    "NYC-Parks-Public-Events-Upcoming-14-Days/w3wp-dpdi"
)
TIMEZONE_NAME = "America/New_York"
NYC = ZoneInfo(TIMEZONE_NAME)
PAGE_SIZE = 1000
MAX_PAGES = 50
REQUEST_TIMEOUT_SECONDS = 40
OUTPUT_ROOT = Path(__file__).resolve().parent / "data" / "nyc_parks"

IMPORTANT_FIELDS = (
    "guid",
    "title",
    "starttime",
    "endtime",
    "categories",
    "park_names",
    "location",
    "coordinates",
    "link",
    "registration_url",
)

CSV_FIELDS = (
    "source_id",
    "guid",
    "title",
    "categories",
    "park_names",
    "park_ids",
    "location",
    "latitude",
    "longitude",
    "coordinates",
    "starttime",
    "endtime",
    "timezone",
    "link",
    "registration_url",
    "registration_description",
    "instructor",
    "contact_phone",
    "image",
    "description",
    "collected_at",
)


def fetch_page(offset: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "$order": "starttime ASC",
            "$limit": PAGE_SIZE,
            "$offset": offset,
        }
    )
    url = f"{ENDPOINT}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "SideQuest-collection/0.1"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"NYC Parks API request failed for offset {offset}: {last_error}") from last_error

    if not isinstance(payload, list):
        raise RuntimeError(f"NYC Parks API returned {type(payload).__name__}, expected a list of events")
    return payload


def fetch_events() -> list[dict]:
    rows: list[dict] = []
    seen_guids: set[str] = set()
    for page_number in range(MAX_PAGES):
        page = fetch_page(page_number * PAGE_SIZE)
        if not page:
            break
        new_rows = []
        for row in page:
            guid = str(row.get("guid") or "").strip()
            if guid and guid in seen_guids:
                continue
            if guid:
                seen_guids.add(guid)
            new_rows.append(row)
        if not new_rows:
            break
        rows.extend(new_rows)
        if len(page) < PAGE_SIZE:
            break
    else:
        raise RuntimeError(f"Stopped after {MAX_PAGES} pages without reaching the end of the feed")
    if not rows:
        raise RuntimeError("NYC Parks API returned no events. Nothing was written.")
    return rows


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value)).replace("\xa0", " ").strip()
    return text or None


def url_of(value: object) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("url"))
    return clean_text(value)


def parse_local_timestamp(value: object) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    parsed = None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    return parsed.replace(tzinfo=NYC).isoformat()


def split_categories(value: object) -> tuple[str | None, list[str]]:
    text = clean_text(value)
    if text is None:
        return None, []
    parts = [part.strip() for part in text.split("|") if part.strip()]
    return text, parts


def parse_coordinates(value: object) -> tuple[str | None, float | None, float | None]:
    text = clean_text(value)
    if text is None:
        return None, None, None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return text, None, None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return text, None, None
    return text, latitude, longitude


def normalize_event(raw: dict, collected_at: str) -> dict:
    categories_raw, categories = split_categories(raw.get("categories"))
    coordinates, latitude, longitude = parse_coordinates(raw.get("coordinates"))
    return {
        "source_id": SOURCE_ID,
        "guid": clean_text(raw.get("guid")),
        "title": clean_text(raw.get("title")),
        "instructor": clean_text(raw.get("instructor")),
        "description": clean_text(raw.get("description")),
        "categories": categories,
        "categories_raw": categories_raw,
        "park_names": clean_text(raw.get("parknames")),
        "park_ids": clean_text(raw.get("parkids")),
        "location": clean_text(raw.get("location")),
        "coordinates": coordinates,
        "latitude": latitude,
        "longitude": longitude,
        "starttime": parse_local_timestamp(raw.get("starttime")),
        "endtime": parse_local_timestamp(raw.get("endtime")),
        "timezone": TIMEZONE_NAME,
        "link": url_of(raw.get("link")),
        "registration_url": url_of(raw.get("registration_url")),
        "registration_description": clean_text(raw.get("registration_description")),
        "contact_phone": clean_text(raw.get("contact_phone")),
        "image": url_of(raw.get("image")),
        "collected_at": collected_at,
    }


def missing_field_counts(events: list[dict]) -> dict[str, int]:
    counts = {field: 0 for field in IMPORTANT_FIELDS}
    for event in events:
        for field in IMPORTANT_FIELDS:
            value = event.get(field)
            if value is None or value == [] or value == "":
                counts[field] += 1
    return counts


def load_previous_snapshot(snapshots_dir: Path) -> tuple[str | None, set[str]]:
    if not snapshots_dir.is_dir():
        return None, set()
    candidates = [path / "events.json" for path in snapshots_dir.iterdir() if (path / "events.json").is_file()]
    if not candidates:
        return None, set()
    previous_file = max(candidates, key=lambda path: path.stat().st_mtime)
    previous_events = json.loads(previous_file.read_text(encoding="utf-8"))
    guids = {str(event.get("guid")) for event in previous_events if event.get("guid")}
    return previous_file.parent.name, guids


def events_new_since(events: list[dict], previous_guids: set[str], has_previous: bool) -> list[dict]:
    if not has_previous:
        return []
    return [event for event in events if event.get("guid") and event["guid"] not in previous_guids]


def csv_row(event: dict) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in CSV_FIELDS:
        value = event.get(field)
        if field == "categories" and isinstance(value, list):
            row[field] = " | ".join(value)
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


def write_bundle(directory: Path, events: list[dict], manifest: dict, new_since: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "events.json", events)
    write_csv(directory / "events.csv", events)
    write_json(directory / "manifest.json", manifest)
    write_json(directory / "new_since_last_run.json", new_since)


def build_manifest(events: list[dict], collected_at: str, is_baseline: bool) -> dict:
    start_times = [event["starttime"] for event in events if event.get("starttime")]
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "dataset_url": DATASET_URL,
        "endpoint": ENDPOINT,
        "collected_at": collected_at,
        "timezone": TIMEZONE_NAME,
        "filters": {
            "window": "upcoming 14 days",
            "order": "starttime ASC",
        },
        "row_count": len(events),
        "earliest_starttime": min(start_times) if start_times else None,
        "latest_starttime": max(start_times) if start_times else None,
        "missing_field_counts": missing_field_counts(events),
        "notes": [
            "Blank CSV cells are null. JSON uses null for unknown values.",
            "This source has no price field. A public event is not recorded as free.",
            "starttime and endtime are interpreted as America/New_York.",
            "The feed is a rolling 14-day window refreshed by NYC Parks, not a historical archive.",
            (
                "This run is the first snapshot, so no event is marked new today."
                if is_baseline
                else "new_since_last_run.json lists guids that were absent from the previous snapshot."
            ),
        ],
    }


def build_new_since(
    events: list[dict],
    new_events: list[dict],
    collected_at: str,
    previous_snapshot: str | None,
) -> dict:
    is_baseline = previous_snapshot is None
    if is_baseline:
        note = (
            "First collection establishes a baseline of the current 14-day window. "
            "The full pull is in events.json and events.csv. These rows are not marked "
            "as new today because there is no previous snapshot to compare."
        )
    else:
        note = (
            f"Compared with snapshot {previous_snapshot}. "
            "An event is new when its guid was not in that snapshot."
        )
    return {
        "collected_at": collected_at,
        "compared_to_snapshot": previous_snapshot,
        "is_baseline": is_baseline,
        "current_event_count": len(events),
        "new_event_count": len(new_events),
        "note": note,
        "new_events": new_events,
    }


def main() -> int:
    collected_at = datetime.now(NYC).isoformat()
    snapshot_day = datetime.now(NYC).date().isoformat()
    snapshots_dir = OUTPUT_ROOT / "snapshots"
    previous_snapshot, previous_guids = load_previous_snapshot(snapshots_dir)

    raw_rows = fetch_events()
    events = [normalize_event(row, collected_at) for row in raw_rows]
    new_events = events_new_since(events, previous_guids, previous_snapshot is not None)
    manifest = build_manifest(events, collected_at, previous_snapshot is None)
    new_since = build_new_since(events, new_events, collected_at, previous_snapshot)

    write_bundle(OUTPUT_ROOT / "latest", events, manifest, new_since)
    write_bundle(snapshots_dir / snapshot_day, events, manifest, new_since)

    print(f"Collected {len(events)} NYC Parks events at {collected_at}")
    print(f"Wrote {OUTPUT_ROOT / 'latest'}")
    print(f"Wrote {snapshots_dir / snapshot_day}")
    if previous_snapshot is None:
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
