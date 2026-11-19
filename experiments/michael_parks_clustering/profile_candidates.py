#!/usr/bin/env python3
"""Profile saved K-means candidates for k=2, 3, and 4.

Loads output/kmeans_candidates.joblib and the saved split. It does not fit
KMeans, change the split, or change the geographic multiplier.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from joblib import load

from fit_clusters import ACTIVITIES_PATH, MODEL_PATH, OUTPUT_DIR, transform
from fit_clusters import total_sse
from prepare_activities import EARTH_RADIUS_KM

PROFILE_PATH = OUTPUT_DIR / "candidate_profiles_k234.json"
K_VALUES = (2, 3, 4)
VERY_SMALL_TRAINING_COUNT = 10


def load_activities(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    activities = {}
    for row in rows:
        activities[row["activity_id"]] = {
            "activity_id": row["activity_id"],
            "title": row["title"],
            "location": row["location"],
            "categories": json.loads(row["categories_json"]),
            "latitude": float(row["latitude"]) if row["latitude"] else None,
            "longitude": float(row["longitude"]) if row["longitude"] else None,
        }
    return activities


def rows_for(activities: dict[str, dict], activity_ids: list[str]) -> list[dict]:
    missing = [activity_id for activity_id in activity_ids if activity_id not in activities]
    if missing:
        raise SystemExit(f"Saved split ids are missing from activities.csv: {missing[:5]}")
    return [activities[activity_id] for activity_id in activity_ids]


def inverse_project(weighted_easting: float, weighted_northing: float, preprocessing: dict) -> dict:
    multiplier = float(preprocessing["geographic_multiplier"])
    if multiplier == 0.0:
        raise SystemExit("Saved geographic multiplier is 0. The center cannot be converted back to degrees.")
    easting_km = weighted_easting / multiplier
    northing_km = weighted_northing / multiplier
    origin_latitude = float(preprocessing["origin_latitude"])
    origin_longitude = float(preprocessing["origin_longitude"])
    latitude = origin_latitude + math.degrees(northing_km / EARTH_RADIUS_KM)
    longitude = origin_longitude + math.degrees(
        easting_km / (EARTH_RADIUS_KM * math.cos(math.radians(origin_latitude)))
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "easting_km": easting_km,
        "northing_km": northing_km,
        "source": "Last two coordinates of the saved center, divided by the saved multiplier, then inverted with the saved equirectangular projection.",
    }


def top_categories(members: list[dict]) -> list[dict]:
    counts: Counter[str] = Counter()
    for member in members:
        for label in member["categories"]:
            counts[label] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    total = len(members)
    return [
        {
            "category": label,
            "training_members": count,
            "training_membership_percentage": (100.0 * count / total) if total else None,
        }
        for label, count in ranked
    ]


def nearest_training(center: np.ndarray, vectors: np.ndarray, rows: list[dict]) -> list[dict]:
    squared = ((vectors - center) ** 2).sum(axis=1)
    order = np.argsort(squared, kind="mergesort")
    chosen = []
    for index in order[:3]:
        row = rows[int(index)]
        chosen.append(
            {
                "activity_id": row["activity_id"],
                "title": row["title"],
                "location": row["location"],
                "categories": row["categories"],
                "squared_distance_to_center": float(squared[int(index)]),
            }
        )
    return chosen


def profile_k(k: int, model, train_rows: list[dict], test_rows: list[dict], train_vectors: np.ndarray, test_vectors: np.ndarray, preprocessing: dict) -> dict:
    centers = np.asarray(model.cluster_centers_, dtype=float)
    if centers.shape[0] != k:
        raise SystemExit(f"Saved model for k={k} has {centers.shape[0]} centers.")
    _train_sse, train_labels = total_sse(train_vectors, centers)
    _test_sse, test_labels = total_sse(test_vectors, centers)
    if not np.array_equal(train_labels, np.asarray(model.labels_)):
        raise SystemExit(f"Training assignments for k={k} do not match the saved model labels.")
    clusters = []
    for cluster_id in range(k):
        train_members = [row for row, label in zip(train_rows, train_labels) if int(label) == cluster_id]
        test_members = [row for row, label in zip(test_rows, test_labels) if int(label) == cluster_id]
        training_count = len(train_members)
        test_count = len(test_members)
        clusters.append(
            {
                "cluster_id": cluster_id,
                "training_count": training_count,
                "test_count": test_count,
                "total_count": training_count + test_count,
                "top_training_categories": top_categories(train_members),
                "geographic_center": inverse_project(float(centers[cluster_id, -2]), float(centers[cluster_id, -1]), preprocessing),
                "nearest_training_activities": nearest_training(centers[cluster_id], train_vectors, train_rows),
                "empty": training_count + test_count == 0,
                "very_small": training_count < VERY_SMALL_TRAINING_COUNT,
            }
        )
    return {
        "k": k,
        "very_small_rule": f"training_count < {VERY_SMALL_TRAINING_COUNT}",
        "clusters": clusters,
    }


def write_markdown(path: Path, profiles: list[dict]) -> None:
    lines = [
        "# Candidate profiles for k=2, 3, and 4",
        "",
        "Assignments use the saved centers. The models were not refit.",
        f"A cluster is very small when its training count is below {VERY_SMALL_TRAINING_COUNT}.",
        "Geographic centers are the saved center's coordinate pair converted back to degrees.",
        "Category percentages use training members of that cluster.",
        "",
    ]
    for profile in profiles:
        lines.append(f"## k={profile['k']}")
        lines.append("")
        for cluster in profile["clusters"]:
            lines.append(
                f"### Cluster {cluster['cluster_id']}: "
                f"{cluster['training_count']} training, {cluster['test_count']} test, {cluster['total_count']} total"
            )
            lines.append("")
            center = cluster["geographic_center"]
            lines.append(f"Center: {center['latitude']:.6f}, {center['longitude']:.6f}")
            lines.append("")
            lines.append("| Category | Training members | Training membership |")
            lines.append("| --- | ---: | ---: |")
            for item in cluster["top_training_categories"]:
                lines.append(
                    f"| {item['category']} | {item['training_members']} | {item['training_membership_percentage']:.1f}% |"
                )
            lines.append("")
            lines.append("Nearest training activities:")
            lines.append("")
            for activity in cluster["nearest_training_activities"]:
                labels = ", ".join(activity["categories"])
                lines.append(f"- {activity['title']} — {activity['location']} — {labels}")
            lines.append("")
        flagged = [cluster for cluster in profile["clusters"] if cluster["empty"] or cluster["very_small"]]
        if flagged:
            rendered = ", ".join(
                f"{cluster['cluster_id']} (training {cluster['training_count']}, test {cluster['test_count']})"
                for cluster in flagged
            )
            lines.append(f"Empty or very small: {rendered}")
        else:
            lines.append("Empty or very small: none")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    saved = load(MODEL_PATH)
    preprocessing = saved["preprocessing"]
    activities = load_activities(ACTIVITIES_PATH)
    train_rows = rows_for(activities, saved["train_activity_ids"])
    test_rows = rows_for(activities, saved["test_activity_ids"])
    train_vectors, _train_unseen = transform(train_rows, preprocessing)
    test_vectors, _test_unseen = transform(test_rows, preprocessing)
    profiles = [
        profile_k(
            k,
            saved["models"][k],
            train_rows,
            test_rows,
            train_vectors,
            test_vectors,
            preprocessing,
        )
        for k in K_VALUES
    ]
    payload = {
        "source_model": "output/kmeans_candidates.joblib",
        "retrained": False,
        "geographic_multiplier": preprocessing["geographic_multiplier"],
        "very_small_training_count_below": VERY_SMALL_TRAINING_COUNT,
        "profiles": profiles,
    }
    PROFILE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(OUTPUT_DIR / "candidate_profiles_k234.md", profiles)
    print(f"geographic_multiplier={preprocessing['geographic_multiplier']:.16f}")
    print(f"wrote {PROFILE_PATH}")
    for profile in profiles:
        print(f"k={profile['k']}")
        for cluster in profile["clusters"]:
            print(
                f"  cluster {cluster['cluster_id']}: "
                f"train={cluster['training_count']} test={cluster['test_count']} total={cluster['total_count']} "
                f"lat={cluster['geographic_center']['latitude']:.6f} "
                f"lon={cluster['geographic_center']['longitude']:.6f} "
                f"very_small={cluster['very_small']}"
            )


if __name__ == "__main__":
    main()
