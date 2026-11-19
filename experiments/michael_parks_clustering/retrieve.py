#!/usr/bin/env python3
"""Retrieve training activities with the saved k=4 model.

The preprocessing and centers come from output/kmeans_candidates.joblib.
This script does not fit KMeans or change the geographic multiplier.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from joblib import load

from fit_clusters import ACTIVITIES_PATH, MODEL_PATH, OUTPUT_DIR, transform, total_sse

EXAMPLE_PATH = OUTPUT_DIR / "example_search.json"
V1_K = 4
TOP_N = 5
CATALOG_NOTE = (
    "Search against the historical NYC Parks catalog collected on 2026-10-13 "
    "for sessions from 2026-10-13 through 2026-10-27. "
    "This is not a statement that any activity is available now."
)
ENCODING_POLICY = (
    "Category labels absent from the training vocabulary are reported and omitted. "
    "They do not add columns. Known labels stay raw 0/1 indicators."
)


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


def load_catalog():
    saved = load(MODEL_PATH)
    preprocessing = saved["preprocessing"]
    model = saved["models"][V1_K]
    centers = np.asarray(model.cluster_centers_, dtype=float)
    if centers.shape[0] != V1_K:
        raise SystemExit(f"Saved k=4 model has {centers.shape[0]} centers.")
    activities = load_activities(ACTIVITIES_PATH)
    train_ids = list(saved["train_activity_ids"])
    test_ids = list(saved["test_activity_ids"])
    if len(train_ids) != 293 or len(test_ids) != 126:
        raise SystemExit("Saved split does not have 293 training and 126 test activities.")
    if set(train_ids) & set(test_ids):
        raise SystemExit("Training and test activity ids overlap.")
    for activity_id in test_ids:
        row = activities[activity_id]
        if row["latitude"] is None or row["longitude"] is None:
            raise SystemExit(f"Test activity {activity_id} is missing coordinates.")
    train_rows = [activities[activity_id] for activity_id in train_ids]
    if any(row["latitude"] is None or row["longitude"] is None for row in train_rows):
        raise SystemExit("A training activity is missing coordinates.")
    train_vectors, unseen = transform(train_rows, preprocessing)
    if unseen:
        raise SystemExit("Training rows produced labels outside the saved vocabulary.")
    _sse, assigned = total_sse(train_vectors, centers)
    if not np.array_equal(assigned, np.asarray(model.labels_)):
        raise SystemExit("Training assignments do not match the saved k=4 labels.")
    return {
        "preprocessing": preprocessing,
        "centers": centers,
        "train_rows": train_rows,
        "train_vectors": train_vectors,
        "train_labels": assigned,
        "test_ids": test_ids,
        "activities": activities,
    }


def encode_query(categories: list[str], latitude: float, longitude: float, preprocessing: dict) -> tuple[np.ndarray, list[str]]:
    vector, unseen = transform(
        [
            {
                "activity_id": "query",
                "title": "query",
                "categories": list(categories),
                "latitude": float(latitude),
                "longitude": float(longitude),
            }
        ],
        preprocessing,
    )
    unknown = unseen[0]["unseen_labels"] if unseen else []
    return vector[0], unknown


def ranked_hits(query: np.ndarray, vectors: np.ndarray, rows: list[dict], limit: int) -> list[dict]:
    squared = ((vectors - query) ** 2).sum(axis=1)
    order = sorted(range(len(rows)), key=lambda index: (float(squared[index]), rows[index]["activity_id"]))
    hits = []
    for rank, index in enumerate(order[:limit], start=1):
        row = rows[index]
        hits.append(
            {
                "rank": rank,
                "activity_id": row["activity_id"],
                "title": row["title"],
                "location": row["location"],
                "distance": float(squared[index]) ** 0.5,
            }
        )
    return hits


def assign_cluster(query: np.ndarray, centers: np.ndarray) -> int:
    squared = ((centers - query) ** 2).sum(axis=1)
    return min(range(len(centers)), key=lambda index: (float(squared[index]), index))


def search(categories: list[str], latitude: float, longitude: float, catalog: dict) -> dict:
    query, unknown = encode_query(categories, latitude, longitude, catalog["preprocessing"])
    train_rows = catalog["train_rows"]
    train_vectors = catalog["train_vectors"]
    baseline_hits = ranked_hits(query, train_vectors, train_rows, TOP_N)
    cluster_id = assign_cluster(query, catalog["centers"])
    pool_indexes = [index for index, label in enumerate(catalog["train_labels"]) if int(label) == cluster_id]
    pool_rows = [train_rows[index] for index in pool_indexes]
    pool_vectors = train_vectors[pool_indexes]
    v1_hits = ranked_hits(query, pool_vectors, pool_rows, TOP_N)
    baseline_ids = [hit["activity_id"] for hit in baseline_hits]
    v1_ids = [hit["activity_id"] for hit in v1_hits]
    overlap = len(set(baseline_ids) & set(v1_ids))
    return {
        "unknown_labels": unknown,
        "encoding_policy": ENCODING_POLICY,
        "baseline": {
            "candidate_pool_size": len(train_rows),
            "distance_calculations": len(train_rows),
            "results": baseline_hits,
        },
        "v1": {
            "cluster": cluster_id,
            "candidate_pool_size": len(pool_rows),
            "centroid_comparisons": int(catalog["centers"].shape[0]),
            "distance_calculations": int(catalog["centers"].shape[0]) + len(pool_rows),
            "results": v1_hits,
        },
        "top5_overlap": overlap,
        "recall_against_exhaustive_retrieval": overlap / TOP_N,
    }


def example_payload(result: dict) -> dict:
    return {
        "catalog_note": CATALOG_NOTE,
        "query_note": "Explicitly hypothetical search profile. It is not an observed user search.",
        "query": {
            "categories": ["Fitness", "Exercise Classes"],
            "latitude": 40.73,
            "longitude": -73.94,
        },
        "tie_break": "Equal feature-space distances keep the lexicographically smaller activity id.",
        "distance": "Euclidean distance in the saved training feature space.",
        **result,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    catalog = load_catalog()
    result = search(["Fitness", "Exercise Classes"], 40.73, -73.94, catalog)
    payload = example_payload(result)
    EXAMPLE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"unknown_labels={payload['unknown_labels']}")
    print(f"v1_cluster={payload['v1']['cluster']} pool={payload['v1']['candidate_pool_size']}")
    print("baseline:")
    for hit in payload["baseline"]["results"]:
        print(f"  {hit['rank']} {hit['distance']:.6f} {hit['activity_id']} | {hit['title']} | {hit['location']}")
    print("v1:")
    for hit in payload["v1"]["results"]:
        print(f"  {hit['rank']} {hit['distance']:.6f} {hit['activity_id']} | {hit['title']} | {hit['location']}")
    print(f"wrote {EXAMPLE_PATH}")


if __name__ == "__main__":
    main()
