#!/usr/bin/env python3
"""Build an activity-level table from the local NYC Parks events file.

Reads data/nyc_parks/latest/events.json and writes derived files in this
folder. It does not call an API, connect to a database, or edit the source.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = EXPERIMENT_DIR.parents[1]
SOURCE_PATH = REPOSITORY_DIR / "data" / "nyc_parks" / "latest" / "events.json"
OUTPUT_DIR = EXPERIMENT_DIR / "output"

EARTH_RADIUS_KM = 6371.0
VIRTUAL_LOCATION_WORDS = ("virtual", "online")


def normalize_label(value: str) -> str:
    """Case- and punctuation-insensitive key for title or location text."""
    text = unicodedata.normalize("NFKC", value)
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    text = text.casefold()
    text = re.sub(r"[^0-9a-z]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_description(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    return re.sub(r"\s+", " ", text).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def activity_id_for(normalized_title: str, normalized_location: str, signature: str) -> str:
    payload = f"{normalized_title}\n{normalized_location}\n{signature}".encode("utf-8")
    return "act_" + hashlib.sha256(payload).hexdigest()[:12]


def parse_points(coordinates: str | None) -> list[tuple[float, float]]:
    if not coordinates:
        return []
    points: list[tuple[float, float]] = []
    for piece in coordinates.split(";"):
        parts = [part.strip() for part in piece.split(",")]
        if len(parts) != 2:
            continue
        try:
            latitude = float(parts[0])
            longitude = float(parts[1])
        except ValueError:
            continue
        points.append((latitude, longitude))
    return points


def calendar_date(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    return timestamp[:10]


def choose_representative(values: list[str]) -> str:
    counts = Counter(values)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def sets_are_nested(category_sets: list[frozenset[str]]) -> bool:
    unique_sets = list({category_set for category_set in category_sets})
    for left in unique_sets:
        for right in unique_sets:
            if not (left <= right or right <= left):
                return False
    return True


def resolved_categories(sessions: list[dict]) -> tuple[list[str], str]:
    lists = [tuple(session.get("categories") or []) for session in sessions]
    unique_lists = set(lists)
    if len(unique_lists) == 1:
        return list(lists[0]), "consistent"
    counts = Counter(lists)
    base = list(sorted(counts, key=lambda value: (-counts[value], value))[0])
    extras = sorted(set().union(*unique_lists) - set(base))
    return base + extras, "inconsistent_nested_labels"


def location_is_virtual(location: str) -> bool:
    normalized = normalize_label(location)
    return any(word in normalized.split() for word in VIRTUAL_LOCATION_WORDS)


def population_variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def project(latitude: float, longitude: float, origin_lat: float, origin_lon: float) -> tuple[float, float]:
    origin_lat_radians = math.radians(origin_lat)
    easting_km = (
        EARTH_RADIUS_KM
        * math.cos(origin_lat_radians)
        * math.radians(longitude - origin_lon)
    )
    northing_km = EARTH_RADIUS_KM * math.radians(latitude - origin_lat)
    return easting_km, northing_km


def field_profile(events: list[dict]) -> dict:
    def missing(predicate) -> int:
        return sum(1 for event in events if predicate(event))

    category_lengths = Counter(len(event.get("categories") or []) for event in events)
    return {
        "session_count": len(events),
        "title": {
            "missing": missing(lambda event: not event.get("title")),
            "unique": len({event.get("title") for event in events}),
            "non_ascii_titles": sum(
                1 for event in events if any(ord(character) > 127 for character in event.get("title") or "")
            ),
            "format": "non-null string",
        },
        "categories": {
            "missing_or_empty": missing(lambda event: not event.get("categories")),
            "format": "JSON array of strings, split from categories_raw on '|'",
            "labels_per_session": dict(sorted(category_lengths.items())),
            "unique_labels": len({label for event in events for label in event.get("categories") or []}),
        },
        "location": {
            "missing": missing(lambda event: not event.get("location")),
            "unique": len({event.get("location") for event in events}),
            "format": "free-text site description, often 'room (in Park Name)'",
        },
        "coordinates": {
            "missing_string": missing(lambda event: not event.get("coordinates")),
            "single_point": sum(1 for event in events if len(parse_points(event.get("coordinates"))) == 1),
            "multiple_points": sum(1 for event in events if len(parse_points(event.get("coordinates"))) > 1),
            "unparsed": sum(1 for event in events if event.get("coordinates") and not parse_points(event.get("coordinates"))),
            "latitude_missing": missing(lambda event: event.get("latitude") is None),
            "longitude_missing": missing(lambda event: event.get("longitude") is None),
            "format": "one 'latitude, longitude' pair, or two pairs separated by ';'",
        },
        "time": {
            "starttime_missing": missing(lambda event: not event.get("starttime")),
            "endtime_missing": missing(lambda event: not event.get("endtime")),
            "format": "ISO-8601 local timestamp with a numeric offset, timezone field America/New_York",
            "overnight_sessions": sum(
                1
                for event in events
                if event.get("starttime") and event.get("endtime") and event["starttime"][:10] != event["endtime"][:10]
            ),
        },
    }


def build_activities(events: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in events:
        buckets[(normalize_label(event["title"]), normalize_label(event["location"]))].append(event)

    activities: list[dict] = []
    mapping: list[dict] = []
    ambiguous: list[dict] = []

    for (normalized_title, normalized_location), sessions in buckets.items():
        description_groups: dict[str, list[dict]] = defaultdict(list)
        for session in sessions:
            description_groups[normalize_description(session.get("description"))].append(session)

        if len(description_groups) > 1:
            ambiguous.append(
                {
                    "kind": "different_descriptions_under_same_title_and_location",
                    "normalized_title": normalized_title,
                    "normalized_location": normalized_location,
                    "session_count": len(sessions),
                    "description_count": len(description_groups),
                }
            )

        for description_key, described in description_groups.items():
            category_sets = [frozenset(session.get("categories") or []) for session in described]
            if sets_are_nested(category_sets):
                partitions = [described]
            else:
                partitions = []
                by_signature: dict[frozenset[str], list[dict]] = defaultdict(list)
                for session, category_set in zip(described, category_sets):
                    by_signature[category_set].append(session)
                partitions.extend(by_signature.values())
                ambiguous.append(
                    {
                        "kind": "incomparable_category_sets_kept_separate",
                        "title": choose_representative([session["title"] for session in described]),
                        "location": choose_representative([session["location"] for session in described]),
                        "category_sets": [sorted(category_set) for category_set in by_signature],
                        "session_count": len(described),
                    }
                )

            for partition in partitions:
                categories, category_status = resolved_categories(partition)
                if category_status != "consistent":
                    ambiguous.append(
                        {
                            "kind": "nested_category_labels_combined",
                            "title": choose_representative([session["title"] for session in partition]),
                            "location": choose_representative([session["location"] for session in partition]),
                            "session_count": len(partition),
                            "observed_category_lists": [
                                list(category_list)
                                for category_list in sorted({tuple(session.get("categories") or []) for session in partition})
                            ],
                            "resolved_categories": categories,
                        }
                    )
                point_sets = []
                for session in partition:
                    points = parse_points(session.get("coordinates"))
                    point_sets.append(tuple(points))
                unique_point_sets = set(point_sets)
                if len(unique_point_sets) == 1 and len(next(iter(unique_point_sets))) == 1:
                    latitude, longitude = next(iter(unique_point_sets))[0]
                    coordinate_status = "single_point"
                elif any(len(points) > 1 for points in point_sets) or len(unique_point_sets) > 1:
                    latitude, longitude = None, None
                    coordinate_status = "multiple_or_disagreeing_points"
                else:
                    latitude, longitude = None, None
                    coordinate_status = "missing"
                title = choose_representative([session["title"] for session in partition])
                location = choose_representative([session["location"] for session in partition])
                virtual = location_is_virtual(location)
                reasons: list[str] = []
                if not categories:
                    reasons.append("no_category_labels")
                if coordinate_status != "single_point":
                    reasons.append("no_single_measured_point")
                if virtual:
                    reasons.append("location_text_is_virtual_or_online")
                signature = "title-location"
                if len(description_groups) > 1:
                    signature += "|description:" + hashlib.sha256(description_key.encode("utf-8")).hexdigest()[:12]
                if not sets_are_nested(category_sets):
                    signature += "|categories:" + "|".join(sorted(categories))
                activity_id = activity_id_for(normalized_title, normalized_location, signature)
                start_dates = [calendar_date(session.get("starttime")) for session in partition if session.get("starttime")]
                end_dates = [calendar_date(session.get("endtime")) for session in partition if session.get("endtime")]
                activity = {
                    "activity_id": activity_id,
                    "normalized_title": normalized_title,
                    "normalized_location": normalized_location,
                    "title": title,
                    "location": location,
                    "categories": categories,
                    "category_status": category_status,
                    "description": choose_representative([session.get("description") or "" for session in partition]),
                    "session_count": len(partition),
                    "latitude": latitude,
                    "longitude": longitude,
                    "coordinate_status": coordinate_status,
                    "location_text_role": "virtual_or_online" if virtual else "site_text",
                    "model_ready": not reasons,
                    "exclusion_reasons": reasons,
                    "earliest_session_date": min(start_dates or end_dates),
                    "latest_session_date": max(start_dates or end_dates),
                    "park_ids": sorted({session.get("park_ids") for session in partition if session.get("park_ids")}),
                    "park_names": sorted({session.get("park_names") for session in partition if session.get("park_names")}),
                }
                activities.append(activity)
                for session in partition:
                    start = session.get("starttime")
                    end = session.get("endtime")
                    if start:
                        session_date = calendar_date(start)
                        date_basis = "starttime"
                    else:
                        session_date = calendar_date(end)
                        date_basis = "endtime"
                    mapping.append(
                        {
                            "activity_id": activity_id,
                            "guid": session["guid"],
                            "source_id": session.get("source_id"),
                            "title": session.get("title"),
                            "location": session.get("location"),
                            "categories": session.get("categories") or [],
                            "starttime": start,
                            "endtime": end,
                            "session_date": session_date,
                            "session_date_basis": date_basis,
                            "coordinates": session.get("coordinates"),
                            "latitude": session.get("latitude"),
                            "longitude": session.get("longitude"),
                            "park_ids": session.get("park_ids"),
                            "park_names": session.get("park_names"),
                        }
                    )
    activities.sort(key=lambda activity: activity["activity_id"])
    mapping.sort(key=lambda row: (row["activity_id"], row["session_date"] or "", row["guid"]))
    return activities, mapping, ambiguous


def write_activities(path: Path, activities: list[dict]) -> None:
    fields = [
        "activity_id",
        "title",
        "location",
        "normalized_title",
        "normalized_location",
        "categories_json",
        "category_status",
        "session_count",
        "earliest_session_date",
        "latest_session_date",
        "latitude",
        "longitude",
        "coordinate_status",
        "location_text_role",
        "model_ready",
        "exclusion_reasons_json",
        "park_ids_json",
        "park_names_json",
        "description",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for activity in activities:
            writer.writerow(
                {
                    "activity_id": activity["activity_id"],
                    "title": activity["title"],
                    "location": activity["location"],
                    "normalized_title": activity["normalized_title"],
                    "normalized_location": activity["normalized_location"],
                    "categories_json": json.dumps(activity["categories"], ensure_ascii=False),
                    "category_status": activity["category_status"],
                    "session_count": activity["session_count"],
                    "earliest_session_date": activity["earliest_session_date"],
                    "latest_session_date": activity["latest_session_date"],
                    "latitude": "" if activity["latitude"] is None else f"{activity['latitude']:.10f}",
                    "longitude": "" if activity["longitude"] is None else f"{activity['longitude']:.10f}",
                    "coordinate_status": activity["coordinate_status"],
                    "location_text_role": activity["location_text_role"],
                    "model_ready": "true" if activity["model_ready"] else "false",
                    "exclusion_reasons_json": json.dumps(activity["exclusion_reasons"]),
                    "park_ids_json": json.dumps(activity["park_ids"], ensure_ascii=False),
                    "park_names_json": json.dumps(activity["park_names"], ensure_ascii=False),
                    "description": activity["description"],
                }
            )


def write_mapping(path: Path, mapping: list[dict]) -> None:
    fields = [
        "activity_id",
        "guid",
        "source_id",
        "title",
        "location",
        "categories_json",
        "starttime",
        "endtime",
        "session_date",
        "session_date_basis",
        "coordinates",
        "latitude",
        "longitude",
        "park_ids",
        "park_names",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in mapping:
            writer.writerow(
                {
                    "activity_id": row["activity_id"],
                    "guid": row["guid"],
                    "source_id": row["source_id"] or "",
                    "title": row["title"],
                    "location": row["location"],
                    "categories_json": json.dumps(row["categories"], ensure_ascii=False),
                    "starttime": row["starttime"] or "",
                    "endtime": row["endtime"] or "",
                    "session_date": row["session_date"] or "",
                    "session_date_basis": row["session_date_basis"],
                    "coordinates": row["coordinates"] or "",
                    "latitude": "" if row["latitude"] is None else row["latitude"],
                    "longitude": "" if row["longitude"] is None else row["longitude"],
                    "park_ids": row["park_ids"] or "",
                    "park_names": row["park_names"] or "",
                }
            )


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def build_feature_table(activities: list[dict]) -> tuple[list[str], list[dict], dict]:
    ready = [activity for activity in activities if activity["model_ready"]]
    vocabulary = sorted({label for activity in ready for label in activity["categories"]})
    origin_lat = median([activity["latitude"] for activity in ready])
    origin_lon = median([activity["longitude"] for activity in ready])
    rows: list[dict] = []
    for activity in ready:
        easting_km, northing_km = project(
            activity["latitude"], activity["longitude"], origin_lat, origin_lon
        )
        encoded = {f"category:{label}": 1 if label in set(activity["categories"]) else 0 for label in vocabulary}
        encoded["activity_id"] = activity["activity_id"]
        encoded["easting_km"] = easting_km
        encoded["northing_km"] = northing_km
        rows.append(encoded)

    category_columns = [f"category:{label}" for label in vocabulary]
    category_variance = 0.0
    for column in category_columns:
        category_variance += population_variance([float(row[column]) for row in rows])
    location_variance = population_variance([row["easting_km"] for row in rows]) + population_variance(
        [row["northing_km"] for row in rows]
    )
    if location_variance == 0:
        raise RuntimeError("Location variance is zero; the location weight is undefined.")
    location_weight = math.sqrt(category_variance / location_variance)
    for row in rows:
        row["easting_km_weighted"] = location_weight * row["easting_km"]
        row["northing_km_weighted"] = location_weight * row["northing_km"]

    specification = {
        "algorithm": "K-means on Euclidean distance. This file specifies the vectors only; no model is fit and k is not chosen.",
        "rows": "one model-ready activity",
        "category_encoding": "multi-hot indicators named category:<label>. A listed label is 1 and every other vocabulary label is 0. Labels are not ordinal and are not a single class id.",
        "category_vocabulary": vocabulary,
        "category_scaling": "Category columns are not standardized. Standardizing each column would increase the influence of rare labels because their variance is small.",
        "location_encoding": {
            "projection": "equirectangular kilometers from a fixed origin",
            "earth_radius_km": EARTH_RADIUS_KM,
            "origin_latitude": origin_lat,
            "origin_longitude": origin_lon,
            "origin_rule": "coordinate-wise median of model-ready activities; even counts use the mean of the two central values",
            "easting_km": "6371 * cos(origin_latitude) * radians(longitude - origin_longitude)",
            "northing_km": "6371 * radians(latitude - origin_latitude)",
            "approximation": "This treats Earth as a sphere and ignores elevation. It is a representation, not a surveyed distance.",
        },
        "relative_weighting": {
            "rule": "Multiply both location columns by one scalar so the two weighted location columns have the same total population variance as all category columns combined.",
            "population_variance": "sum((value - mean)^2) / n, using the same divisor for every column",
            "category_block_variance": category_variance,
            "location_block_variance_before_weight": location_variance,
            "location_weight": location_weight,
            "model_vector": ["category:<label> for each vocabulary label, in alphabetical order", "location_weight * easting_km", "location_weight * northing_km"],
            "assumption": "Equal total variance is a modeling choice that stops kilometers from dominating binary labels, or the reverse. It is not a measured statement that category and location matter equally.",
            "one_label_equivalent_km": 1.0 / location_weight,
            "one_label_reading": "A one-column category difference has squared Euclidean length 1. The same squared length comes from a location difference of 1/location_weight kilometers along one projected axis, with the other axis unchanged.",
        },
        "excluded_from_numeric_features": ["title", "normalized_title", "guid", "source_id", "activity_id", "description", "session times"],
        "not_used_in_this_experiment": ["session time", "park id prefix as a borough", "text of the description"],
    }
    columns = ["activity_id", *category_columns, "easting_km", "northing_km", "easting_km_weighted", "northing_km_weighted"]
    return columns, rows, specification


def write_feature_matrix(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            output = {}
            for column in columns:
                value = row[column]
                if isinstance(value, float):
                    output[column] = f"{value:.8f}"
                else:
                    output[column] = value
            writer.writerow(output)


def titles_at_multiple_locations(events: list[dict]) -> int:
    locations: dict[str, set[str]] = defaultdict(set)
    for event in events:
        locations[normalize_label(event["title"])].add(normalize_label(event["location"]))
    return sum(1 for grouped in locations.values() if len(grouped) > 1)


def main() -> None:
    if not SOURCE_PATH.is_file():
        raise SystemExit(f"Missing source file: {SOURCE_PATH}")
    events = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    guids = [event.get("guid") for event in events]
    if any(not guid for guid in guids) or len(guids) != len(set(guids)):
        raise SystemExit("Expected every session to have a unique guid.")
    activities, mapping, ambiguous = build_activities(events)
    if len(mapping) != len(events):
        raise SystemExit("Every source session must appear exactly once in the mapping.")
    activity_ids = [activity["activity_id"] for activity in activities]
    if len(activity_ids) != len(set(activity_ids)):
        raise SystemExit("Activity ids collided; the grouping signature is not unique.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_activities(OUTPUT_DIR / "activities.csv", activities)
    write_mapping(OUTPUT_DIR / "session_mapping.csv", mapping)
    columns, feature_rows, specification = build_feature_table(activities)
    write_feature_matrix(OUTPUT_DIR / "feature_matrix.csv", columns, feature_rows)
    (OUTPUT_DIR / "model_specification.json").write_text(
        json.dumps(specification, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "ambiguous_cases.json").write_text(
        json.dumps(ambiguous, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    reason_counts: Counter[str] = Counter()
    for activity in activities:
        if not activity["exclusion_reasons"]:
            reason_counts["model_ready"] += 1
        for reason in activity["exclusion_reasons"]:
            reason_counts[reason] += 1
    exact_pairs = len({(event["title"], event["location"]) for event in events})
    normalized_pairs = len({(normalize_label(event["title"]), normalize_label(event["location"])) for event in events})
    summary = {
        "source_path": str(SOURCE_PATH),
        "source_sha256": sha256_file(SOURCE_PATH),
        "source_session_count": len(events),
        "activity_count": len(activities),
        "mapped_session_count": len(mapping),
        "model_ready_activity_count": sum(1 for activity in activities if activity["model_ready"]),
        "excluded_activity_count": sum(1 for activity in activities if not activity["model_ready"]),
        "exclusion_reason_activity_counts": dict(sorted(reason_counts.items())),
        "exact_title_location_pairs": exact_pairs,
        "normalized_title_location_pairs": normalized_pairs,
        "normalized_key_changed_any_grouping": exact_pairs != normalized_pairs,
        "titles_kept_separate_across_locations": titles_at_multiple_locations(events),
        "ambiguous_case_count": len(ambiguous),
        "field_profile": field_profile(events),
        "feature_column_count_excluding_id": len(columns) - 1,
        "category_feature_count": sum(1 for column in columns if column.startswith("category:")),
        "location_weight": specification["relative_weighting"]["location_weight"],
        "origin_latitude": specification["location_encoding"]["origin_latitude"],
        "origin_longitude": specification["location_encoding"]["origin_longitude"],
    }
    (OUTPUT_DIR / "preparation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in (
        "source_session_count",
        "activity_count",
        "model_ready_activity_count",
        "excluded_activity_count",
        "exclusion_reason_activity_counts",
        "ambiguous_case_count",
        "location_weight",
        "category_feature_count",
    )}, indent=2))


if __name__ == "__main__":
    main()
