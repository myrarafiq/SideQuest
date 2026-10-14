#!/usr/bin/env python3
"""Collect a small Google Places sample for outdoor activities in Manhattan and Brooklyn.

Place IDs may be kept and refreshed. Latitude and longitude may be cached for
30 days. Names, addresses, hours, and price levels are saved only as a
short-lived sample so the available fields can be checked. They are not a
permanent venue database. Google Maps attribution is required when those
fields are shown.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_ID = "google-places-api-new"
SOURCE_NAME = "Google Places API (New)"
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
ATTRIBUTION = "Google Maps"
TIMEZONE_NAME = "America/New_York"
NYC = ZoneInfo(TIMEZONE_NAME)
TEXT_QUERIES = ("outdoor activities", "restaurants")
PAGE_SIZE = 10
COORDINATE_RETENTION_DAYS = 30
REQUEST_TIMEOUT_SECONDS = 40
OUTPUT_ROOT = Path(__file__).resolve().parent / "data" / "google_places"
ENV_PATH = Path(__file__).resolve().parent / ".env"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.types",
        "places.primaryType",
        "places.primaryTypeDisplayName",
        "places.businessStatus",
        "places.priceLevel",
        "places.priceRange.startPrice",
        "places.priceRange.endPrice",
        "places.regularOpeningHours.weekdayDescriptions",
        "places.googleMapsUri",
    ]
)

AREAS = (
    {
        "search_area": "Manhattan",
        "low": {"latitude": 40.700292, "longitude": -74.0479},
        "high": {"latitude": 40.882214, "longitude": -73.9070},
    },
    {
        "search_area": "Brooklyn",
        "low": {"latitude": 40.5707, "longitude": -74.0420},
        "high": {"latitude": 40.7395, "longitude": -73.8334},
    },
)
SEARCHES = tuple({**area, "text_query": query} for area in AREAS for query in TEXT_QUERIES)

CSV_FIELDS = (
    "source_id",
    "place_id",
    "name",
    "search_areas",
    "text_query",
    "formatted_address",
    "latitude",
    "longitude",
    "primary_type",
    "types",
    "business_status",
    "price_level",
    "price_currency",
    "price_min",
    "price_max",
    "price_max_unbounded",
    "weekday_hours",
    "google_maps_uri",
    "collected_at",
    "coordinates_delete_after",
    "attribution",
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
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Missing GOOGLE_MAPS_API_KEY. Add it to the environment or to .env in the project root. "
            "Nothing was written."
        )
    return key


def request_json(url: str, body: dict, key: str, field_mask: str) -> dict:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": field_mask,
            "User-Agent": "SideQuest-collection/0.1",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                parsed = json.load(response)
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code in {429, 500, 503} and attempt < 2:
                last_error = RuntimeError(f"HTTP {error.code}: {detail[:500]}")
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"Google Places request failed with HTTP {error.code}: {detail[:800]}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"Google Places request failed: {error}") from error
    else:
        raise RuntimeError(f"Google Places request failed: {last_error}")
    if not isinstance(parsed, dict):
        raise RuntimeError("Google Places returned a response that was not an object")
    return parsed


def search_area(key: str, search: dict) -> list[dict]:
    body = {
        "textQuery": f"{search['text_query']} in {search['search_area']}, New York City",
        "pageSize": PAGE_SIZE,
        "languageCode": "en",
        "regionCode": "US",
        "locationRestriction": {
            "rectangle": {"low": search["low"], "high": search["high"]},
        },
    }
    payload = request_json(ENDPOINT, body, key, FIELD_MASK)
    places = payload.get("places") or []
    if not isinstance(places, list):
        raise RuntimeError("Google Places response did not include a places list")
    for place in places:
        place["_search_area"] = search["search_area"]
        place["_text_query"] = search["text_query"]
    return places


def text_of(value: object) -> str | None:
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def money_amount(money: object) -> tuple[str | None, str | None]:
    if not isinstance(money, dict):
        return None, None
    currency = money.get("currencyCode")
    currency_code = currency.strip() if isinstance(currency, str) and currency.strip() else None
    units = money.get("units")
    nanos = money.get("nanos", 0)
    if units is None and not nanos:
        return None, currency_code
    try:
        whole = int(units or 0)
        fraction = int(nanos or 0)
    except (TypeError, ValueError):
        return None, currency_code
    sign = "-" if whole < 0 or fraction < 0 else ""
    rendered = f"{sign}{abs(whole)}.{abs(fraction):09d}".rstrip("0").rstrip(".")
    return rendered, currency_code


def price_range_of(raw: dict) -> dict:
    price_range = raw.get("priceRange") if isinstance(raw.get("priceRange"), dict) else {}
    start_amount, start_currency = money_amount(price_range.get("startPrice"))
    end_amount, end_currency = money_amount(price_range.get("endPrice"))
    has_start = "startPrice" in price_range
    has_end = "endPrice" in price_range
    currency = start_currency or end_currency
    return {
        "price_currency": currency,
        "price_min": start_amount,
        "price_max": end_amount,
        "price_max_unbounded": has_start and not has_end,
    }


def normalize_place(raw: dict, collected_at: str, delete_after: str) -> dict:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    hours = raw.get("regularOpeningHours") if isinstance(raw.get("regularOpeningHours"), dict) else {}
    weekday = hours.get("weekdayDescriptions")
    weekday_hours = [item.strip() for item in weekday if isinstance(item, str) and item.strip()] if isinstance(weekday, list) else []
    types = [item.strip() for item in raw.get("types", []) if isinstance(item, str) and item.strip()] if isinstance(raw.get("types"), list) else []
    price_level = raw.get("priceLevel")
    if price_level is not None:
        price_level = str(price_level)
    return {
        "source_id": SOURCE_ID,
        "place_id": text_of(raw.get("id")),
        "name": text_of(raw.get("displayName")),
        "search_areas": [raw.get("_search_area")] if raw.get("_search_area") else [],
        "text_query": [raw["_text_query"]] if raw.get("_text_query") else [],
        "formatted_address": text_of(raw.get("formattedAddress")),
        "latitude": latitude if isinstance(latitude, (int, float)) else None,
        "longitude": longitude if isinstance(longitude, (int, float)) else None,
        "primary_type": text_of(raw.get("primaryType")),
        "primary_type_display_name": text_of(raw.get("primaryTypeDisplayName")),
        "types": types,
        "business_status": text_of(raw.get("businessStatus")),
        "price_level": price_level,
        **price_range_of(raw),
        "weekday_hours": weekday_hours,
        "google_maps_uri": text_of(raw.get("googleMapsUri")),
        "collected_at": collected_at,
        "coordinates_delete_after": delete_after,
        "attribution": ATTRIBUTION,
    }


def merge_places(found: list[dict], collected_at: str, delete_after: str) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for raw in found:
        place = normalize_place(raw, collected_at, delete_after)
        place_id = place.get("place_id")
        if not place_id:
            continue
        existing = merged.get(place_id)
        if existing is None:
            merged[place_id] = place
            order.append(place_id)
            continue
        for area in place["search_areas"]:
            if area not in existing["search_areas"]:
                existing["search_areas"].append(area)
        for query in place["text_query"]:
            if query not in existing["text_query"]:
                existing["text_query"].append(query)
    return [merged[place_id] for place_id in order]


def load_previous_ids(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("places") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return {}
    return {record["place_id"]: record for record in records if isinstance(record, dict) and record.get("place_id")}


def update_place_ids(previous: dict[str, dict], places: list[dict], collected_at: str) -> list[dict]:
    updated = dict(previous)
    for place in places:
        place_id = place["place_id"]
        current = updated.get(place_id)
        areas = list(place["search_areas"])
        queries = list(place["text_query"])
        if current is None:
            updated[place_id] = {
                "place_id": place_id,
                "search_areas": areas,
                "text_queries": queries,
                "first_seen_at": collected_at,
                "last_seen_at": collected_at,
            }
            continue
        current["last_seen_at"] = collected_at
        current.pop("text_query", None)
        known_areas = list(current.get("search_areas") or [])
        for area in areas:
            if area not in known_areas:
                known_areas.append(area)
        current["search_areas"] = known_areas
        known_queries = list(current.get("text_queries") or [])
        for query in queries:
            if query not in known_queries:
                known_queries.append(query)
        current["text_queries"] = known_queries
    return list(updated.values())


def csv_row(place: dict) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in CSV_FIELDS:
        value = place.get(field)
        if isinstance(value, list):
            row[field] = " | ".join(str(item) for item in value)
        elif value is None:
            row[field] = ""
        else:
            row[field] = str(value)
    return row


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, places: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for place in places:
            writer.writerow(csv_row(place))


def expire_coordinates(latest_dir: Path, now: datetime) -> None:
    places_path = latest_dir / "places.json"
    manifest_path = latest_dir / "manifest.json"
    if not places_path.is_file() or not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    delete_after = manifest.get("coordinates_delete_after")
    if not isinstance(delete_after, str):
        return
    deadline = datetime.fromisoformat(delete_after)
    if now <= deadline:
        return
    places = json.loads(places_path.read_text(encoding="utf-8"))
    for place in places:
        place["latitude"] = None
        place["longitude"] = None
    write_json(places_path, places)
    write_csv(latest_dir / "places.csv", places)
    manifest["coordinates_expired_at"] = now.isoformat()
    write_json(manifest_path, manifest)


def missing_counts(places: list[dict]) -> dict[str, int]:
    fields = (
        "place_id",
        "name",
        "formatted_address",
        "latitude",
        "longitude",
        "primary_type",
        "price_level",
        "price_min",
        "price_max",
        "weekday_hours",
    )
    counts = {field: 0 for field in fields}
    for place in places:
        for field in fields:
            value = place.get(field)
            if value is None or value == [] or value == "":
                counts[field] += 1
    return counts


def main() -> int:
    key = api_key()
    now = datetime.now(NYC)
    collected_at = now.isoformat()
    delete_after = (now + timedelta(days=COORDINATE_RETENTION_DAYS)).isoformat()
    latest_dir = OUTPUT_ROOT / "latest"
    ids_path = OUTPUT_ROOT / "place_ids.json"
    expire_coordinates(latest_dir, now)

    previous = load_previous_ids(ids_path)
    found: list[dict] = []
    for search in SEARCHES:
        found.extend(search_area(key, search))
    if not found:
        raise RuntimeError("Google Places returned no places. Nothing was written.")

    places = merge_places(found, collected_at, delete_after)
    if not places:
        raise RuntimeError("Google Places returned no place IDs. Nothing was written.")

    previous_ids = set(previous)
    is_baseline = not previous_ids
    new_places = [] if is_baseline else [place for place in places if place["place_id"] not in previous_ids]
    place_ids = update_place_ids(previous, places, collected_at)

    manifest = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "attribution": ATTRIBUTION,
        "endpoint": ENDPOINT,
        "collected_at": collected_at,
        "timezone": TIMEZONE_NAME,
        "filters": {
            "text_queries": list(TEXT_QUERIES),
            "search_areas": [area["search_area"] for area in AREAS],
            "page_size_per_area": PAGE_SIZE,
            "location_restriction": "rectangle",
        },
        "row_count": len(places),
        "missing_field_counts": missing_counts(places),
        "coordinates_delete_after": delete_after,
        "notes": [
            "Attribution required when displaying this content: Google Maps.",
            "place_id may be stored and should be refreshed if it is more than 12 months old.",
            "Latitude and longitude may be cached for 30 days, then deleted. This file records that deadline.",
            "Names, addresses, types, hours, and prices are a field-verification sample, not a permanent venue database.",
            "price_min is Google's inclusive startPrice. price_max is the exclusive endPrice. A missing price_max with price_max_unbounded means Google gave no upper bound.",
            "A missing price range is unknown, not free. price_level is a separate category enum and is not a dollar amount.",
            "search_areas is the query rectangle that returned the place, not a separately verified borough.",
            "Blank CSV cells are null.",
            (
                "This run is the first place-id baseline, so no place is marked new today."
                if is_baseline
                else "new_since_last_run.json lists place IDs that were absent from place_ids.json."
            ),
        ],
    }
    new_since = {
        "collected_at": collected_at,
        "is_baseline": is_baseline,
        "current_place_count": len(places),
        "new_place_count": len(new_places),
        "note": (
            "First collection establishes the place-id baseline. The sample fields are in places.json. "
            "These places are not marked as new today."
            if is_baseline
            else "A place is new when its place_id was not in the previous place_ids.json file."
        ),
        "new_places": new_places,
    }

    latest_dir.mkdir(parents=True, exist_ok=True)
    write_json(latest_dir / "places.json", places)
    write_csv(latest_dir / "places.csv", places)
    write_json(latest_dir / "manifest.json", manifest)
    write_json(latest_dir / "new_since_last_run.json", new_since)
    write_json(
        ids_path,
        {
            "source_id": SOURCE_ID,
            "attribution": ATTRIBUTION,
            "note": "Place IDs only. Refresh IDs older than 12 months with a place-id field request.",
            "places": place_ids,
        },
    )

    print(f"Collected {len(places)} Google Places at {collected_at}")
    priced = sum(1 for place in places if place.get("price_min") is not None or place.get("price_max") is not None)
    print(f"Places with a price range: {priced} of {len(places)}")
    print(f"Wrote {latest_dir}")
    print(f"Wrote {ids_path}")
    if is_baseline:
        print("Baseline run: no places marked as new today.")
    else:
        print(f"New place IDs: {len(new_places)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        raise SystemExit(1)
