#!/usr/bin/env python3
"""Fit K-means candidates on the training split of eligible park activities.

Reads output/activities.csv. Does not read output/feature_matrix.csv, does not
call an API, and does not connect to a database. The full-data preparation
specification stays in output/model_specification.json.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from joblib import dump
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split

from prepare_activities import EARTH_RADIUS_KM, median, population_variance, project

EXPERIMENT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EXPERIMENT_DIR / "output"
ACTIVITIES_PATH = OUTPUT_DIR / "activities.csv"
PREPARATION_SPEC_PATH = OUTPUT_DIR / "model_specification.json"
SPLIT_PATH = OUTPUT_DIR / "data_split.csv"
FITTED_SPEC_PATH = OUTPUT_DIR / "fitted_model_specification.json"
METRICS_PATH = OUTPUT_DIR / "fit_metrics.csv"
PLOT_PATH = OUTPUT_DIR / "elbow.png"
MODEL_PATH = OUTPUT_DIR / "kmeans_candidates.joblib"

RANDOM_STATE = 42
TEST_SIZE = 0.3
EXPECTED_ELIGIBLE = 419
EXPECTED_TRAIN = 293
EXPECTED_TEST = 126
K_VALUES = tuple(range(1, 9))


def load_eligible(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    eligible = []
    for row in rows:
        if row["model_ready"] != "true":
            continue
        if row["exclusion_reasons_json"] != "[]" or row["coordinate_status"] != "single_point":
            raise SystemExit(f"{row['activity_id']} is marked model_ready but fails the coordinate or exclusion flag.")
        if not row["latitude"] or not row["longitude"]:
            raise SystemExit(f"{row['activity_id']} is model_ready without a latitude and longitude.")
        categories = json.loads(row["categories_json"])
        if not categories:
            raise SystemExit(f"{row['activity_id']} is model_ready without category labels.")
        eligible.append(
            {
                "activity_id": row["activity_id"],
                "title": row["title"],
                "categories": categories,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
            }
        )
    ids = [row["activity_id"] for row in eligible]
    if len(ids) != len(set(ids)):
        raise SystemExit("Eligible activity ids are not unique.")
    eligible.sort(key=lambda row: row["activity_id"])
    if len(eligible) != EXPECTED_ELIGIBLE:
        raise SystemExit(f"Expected {EXPECTED_ELIGIBLE} model_ready activities, found {len(eligible)}.")
    return eligible


def split_eligible(eligible: list[dict]) -> tuple[list[dict], list[dict]]:
    indices = np.arange(len(eligible))
    train_index, test_index = train_test_split(
        indices,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=True,
    )
    train_rows = [eligible[int(index)] for index in train_index]
    test_rows = [eligible[int(index)] for index in test_index]
    if len(train_rows) != EXPECTED_TRAIN or len(test_rows) != EXPECTED_TEST:
        raise SystemExit(
            f"Split produced {len(train_rows)} training and {len(test_rows)} test activities, "
            f"expected {EXPECTED_TRAIN} and {EXPECTED_TEST}."
        )
    return train_rows, test_rows


def write_split(path: Path, train_rows: list[dict], test_rows: list[dict]) -> None:
    labeled = [(row["activity_id"], "train") for row in train_rows]
    labeled.extend((row["activity_id"], "test") for row in test_rows)
    labeled.sort(key=lambda item: item[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["activity_id", "split"])
        writer.writeheader()
        for activity_id, split_label in labeled:
            writer.writerow({"activity_id": activity_id, "split": split_label})


def category_vocabulary(rows: list[dict]) -> list[str]:
    labels = {label for row in rows for label in row["categories"]}
    if not labels:
        raise SystemExit("Training activities have no category labels. The multi-hot vocabulary is empty.")
    return sorted(labels)


def column_variance(values: np.ndarray) -> float:
    return population_variance([float(value) for value in values])


def fit_preprocessing(train_rows: list[dict]) -> dict:
    vocabulary = category_vocabulary(train_rows)
    origin_latitude = median([row["latitude"] for row in train_rows])
    origin_longitude = median([row["longitude"] for row in train_rows])
    multi_hot = np.asarray(
        [[1.0 if label in set(row["categories"]) else 0.0 for label in vocabulary] for row in train_rows],
        dtype=float,
    )
    projected = np.asarray(
        [project(row["latitude"], row["longitude"], origin_latitude, origin_longitude) for row in train_rows],
        dtype=float,
    )
    zero_variance_categories = []
    category_variance = 0.0
    for index, label in enumerate(vocabulary):
        variance = column_variance(multi_hot[:, index])
        if variance == 0.0:
            zero_variance_categories.append(label)
        category_variance += variance
    location_variance = column_variance(projected[:, 0]) + column_variance(projected[:, 1])
    if location_variance == 0.0:
        raise SystemExit(
            "Training projected coordinates have population variance 0. "
            "The geographic multiplier divides by that sum, so it is undefined and fitting stopped."
        )
    multiplier = (category_variance / location_variance) ** 0.5
    variance_note = (
        "Zero-variance training category columns are retained as raw 0/1 indicators. "
        "A constant column does not change Euclidean distances, and its population variance adds 0 "
        "to the numerator of the geographic multiplier."
    )
    if category_variance == 0.0:
        variance_note += (
            " The sum of training category variances is 0, so the formula sets the geographic "
            "multiplier to 0 and both weighted coordinate columns are 0 on every row."
        )
    return {
        "vocabulary": vocabulary,
        "origin_latitude": origin_latitude,
        "origin_longitude": origin_longitude,
        "category_block_variance": category_variance,
        "location_block_variance_before_weight": location_variance,
        "geographic_multiplier": multiplier,
        "zero_variance_category_labels": zero_variance_categories,
        "zero_variance_handling": variance_note,
    }


def transform(rows: list[dict], preprocessing: dict) -> tuple[np.ndarray, list[dict]]:
    vocabulary = preprocessing["vocabulary"]
    known = set(vocabulary)
    origin_latitude = preprocessing["origin_latitude"]
    origin_longitude = preprocessing["origin_longitude"]
    multiplier = preprocessing["geographic_multiplier"]
    vectors = []
    unseen_reports = []
    for row in rows:
        present = set(row["categories"])
        unseen = sorted(present - known)
        if unseen:
            unseen_reports.append(
                {
                    "activity_id": row["activity_id"],
                    "title": row["title"],
                    "unseen_labels": unseen,
                }
            )
        multi_hot = [1.0 if label in present else 0.0 for label in vocabulary]
        easting_km, northing_km = project(row["latitude"], row["longitude"], origin_latitude, origin_longitude)
        vectors.append(multi_hot + [multiplier * easting_km, multiplier * northing_km])
    return np.asarray(vectors, dtype=float), unseen_reports


def total_sse(vectors: np.ndarray, centers: np.ndarray) -> tuple[float, np.ndarray]:
    squared = ((vectors[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    labels = squared.argmin(axis=1)
    return float(squared[np.arange(len(vectors)), labels].sum()), labels


def fit_candidates(train_vectors: np.ndarray, test_vectors: np.ndarray) -> tuple[dict[int, KMeans], list[dict]]:
    models: dict[int, KMeans] = {}
    metrics = []
    for k in K_VALUES:
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        model.fit(train_vectors)
        train_sse, _train_labels = total_sse(train_vectors, model.cluster_centers_)
        if abs(train_sse - float(model.inertia_)) > 1e-6:
            raise SystemExit(f"Training SSE for k={k} does not match KMeans inertia_.")
        test_sse, _test_labels = total_sse(test_vectors, model.cluster_centers_)
        models[k] = model
        metrics.append(
            {
                "k": k,
                "train_n": int(train_vectors.shape[0]),
                "test_n": int(test_vectors.shape[0]),
                "train_total_sse": train_sse,
                "test_total_sse": test_sse,
                "train_sse_per_activity": train_sse / train_vectors.shape[0],
                "test_sse_per_activity": test_sse / test_vectors.shape[0],
            }
        )
    return models, metrics


def write_metrics(path: Path, metrics: list[dict]) -> None:
    fields = [
        "k",
        "train_n",
        "test_n",
        "train_total_sse",
        "test_total_sse",
        "train_sse_per_activity",
        "test_sse_per_activity",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in metrics:
            writer.writerow(
                {
                    "k": row["k"],
                    "train_n": row["train_n"],
                    "test_n": row["test_n"],
                    "train_total_sse": f"{row['train_total_sse']:.10f}",
                    "test_total_sse": f"{row['test_total_sse']:.10f}",
                    "train_sse_per_activity": f"{row['train_sse_per_activity']:.10f}",
                    "test_sse_per_activity": f"{row['test_sse_per_activity']:.10f}",
                }
            )


def write_plot(path: Path, metrics: list[dict]) -> None:
    ks = [row["k"] for row in metrics]
    train_n = metrics[0]["train_n"]
    test_n = metrics[0]["test_n"]
    figure, axes = plt.subplots(2, 1, figsize=(8.2, 8.4), sharex=True)
    axes[0].plot(ks, [row["train_total_sse"] for row in metrics], marker="o", label=f"Training total SSE (n={train_n})")
    axes[0].plot(ks, [row["test_total_sse"] for row in metrics], marker="o", label=f"Test total SSE (n={test_n})")
    axes[0].set_ylabel("Total SSE")
    axes[0].legend()
    axes[1].plot(
        ks,
        [row["train_sse_per_activity"] for row in metrics],
        marker="o",
        label=f"Training SSE per activity (n={train_n})",
    )
    axes[1].plot(
        ks,
        [row["test_sse_per_activity"] for row in metrics],
        marker="o",
        label=f"Test SSE per activity (n={test_n})",
    )
    axes[1].set_ylabel("SSE per activity")
    axes[1].set_xlabel("k (number of clusters)")
    axes[1].legend()
    for axis in axes:
        axis.set_xticks(list(K_VALUES))
    figure.suptitle("K-means SSE on the fixed train/test split")
    figure.text(
        0.5,
        0.01,
        "Total SSE adds one squared distance per activity. "
        f"The training total sums {train_n} terms and the test total sums {test_n},\n"
        "so the totals differ partly because the samples have different sizes. "
        "SSE per activity divides each total by its own sample size. No k is selected.",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.08, 1, 0.96))
    figure.savefig(path, dpi=150)
    plt.close(figure)


def preparation_weight(path: Path) -> float | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload["relative_weighting"]["location_weight"])


def write_specification(
    path: Path,
    preprocessing: dict,
    unseen_reports: list[dict],
    train_n: int,
    test_n: int,
) -> dict:
    unused_weight = preparation_weight(PREPARATION_SPEC_PATH)
    multiplier = preprocessing["geographic_multiplier"]
    specification = {
        "document_role": "training_derived_kmeans_fit",
        "distinct_from": (
            "output/model_specification.json is the preparation proposal fit on all 419 "
            "eligible activities. This file replaces that origin, vocabulary, and multiplier "
            "with values calculated from the 293 training activities. The preparation file is unchanged."
        ),
        "not_used": {
            "feature_matrix_csv": "output/feature_matrix.csv was not read.",
            "full_data_geographic_multiplier": unused_weight,
        },
        "split": {
            "source": "activity_id values with model_ready=true in output/activities.csv, sorted, then sklearn train_test_split",
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "shuffle": True,
            "train_n": train_n,
            "test_n": test_n,
            "split_file": "output/data_split.csv",
        },
        "category_encoding": "Raw multi-hot 0/1 columns. Labels are not ordinal ids and columns are not standardized.",
        "category_vocabulary_source": "Distinct category strings on training activities only, sorted alphabetically.",
        "category_vocabulary": preprocessing["vocabulary"],
        "category_dimension": len(preprocessing["vocabulary"]),
        "zero_variance_category_labels": preprocessing["zero_variance_category_labels"],
        "zero_variance_handling": preprocessing["zero_variance_handling"],
        "location_encoding": {
            "projection": "equirectangular kilometers from the training median origin",
            "earth_radius_km": EARTH_RADIUS_KM,
            "origin_latitude": preprocessing["origin_latitude"],
            "origin_longitude": preprocessing["origin_longitude"],
            "origin_rule": "Coordinate-wise median of the 293 training activities. An odd count uses the middle sorted value.",
            "easting_km": "6371 * cos(origin_latitude) * radians(longitude - origin_longitude)",
            "northing_km": "6371 * radians(latitude - origin_latitude)",
        },
        "geographic_multiplier": {
            "formula": "sqrt(sum of training category-column population variances / sum of training projected-coordinate population variances)",
            "population_variance": "sum((value - mean)^2) / n",
            "category_block_variance": preprocessing["category_block_variance"],
            "location_block_variance_before_weight": preprocessing["location_block_variance_before_weight"],
            "value": multiplier,
            "applied_to": "both projected coordinate columns, on training and test",
        },
        "test_application": "Test rows use the saved training vocabulary, origin, and multiplier. Test labels do not enter the vocabulary.",
        "unseen_test_labels": sorted({label for report in unseen_reports for label in report["unseen_labels"]}),
        "test_activities_with_unseen_labels": unseen_reports,
        "test_activities_retained": test_n,
        "kmeans": {
            "k": list(K_VALUES),
            "random_state": RANDOM_STATE,
            "n_init": 10,
            "fit_on": "training vectors only",
            "test_sse": "Sum of squared Euclidean distances from each test vector to the nearest training center. Centers are not refit on test data.",
            "k_selected": None,
        },
    }
    path.write_text(json.dumps(specification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return specification


def print_report(specification: dict, metrics: list[dict]) -> None:
    print(f"train_n={specification['split']['train_n']} test_n={specification['split']['test_n']}")
    print(f"category_dimension={specification['category_dimension']}")
    print(f"geographic_multiplier={specification['geographic_multiplier']['value']:.10f}")
    print(f"origin_latitude={specification['location_encoding']['origin_latitude']:.10f}")
    print(f"origin_longitude={specification['location_encoding']['origin_longitude']:.10f}")
    print(f"zero_variance_category_labels={specification['zero_variance_category_labels']}")
    unseen = specification["unseen_test_labels"]
    affected = specification["test_activities_with_unseen_labels"]
    print(f"unseen_test_labels={unseen}")
    print(f"test_activities_with_unseen_labels={len(affected)}")
    for report in affected:
        print(f"  {report['activity_id']} | {report['title']} | {report['unseen_labels']}")
    print("k,train_total_sse,test_total_sse,train_sse_per_activity,test_sse_per_activity")
    for row in metrics:
        print(
            f"{row['k']},{row['train_total_sse']:.6f},{row['test_total_sse']:.6f},"
            f"{row['train_sse_per_activity']:.6f},{row['test_sse_per_activity']:.6f}"
        )
    print("outputs:")
    for path in (SPLIT_PATH, FITTED_SPEC_PATH, METRICS_PATH, PLOT_PATH, MODEL_PATH):
        print(f"  {path}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if not ACTIVITIES_PATH.is_file():
        raise SystemExit(f"Missing {ACTIVITIES_PATH}")
    eligible = load_eligible(ACTIVITIES_PATH)
    train_rows, test_rows = split_eligible(eligible)
    preprocessing = fit_preprocessing(train_rows)
    train_vectors, train_unseen = transform(train_rows, preprocessing)
    test_vectors, test_unseen = transform(test_rows, preprocessing)
    if train_unseen:
        raise SystemExit("Training rows produced unseen labels. The vocabulary was not built from the training split.")
    if train_vectors.shape[0] != EXPECTED_TRAIN or test_vectors.shape[0] != EXPECTED_TEST:
        raise SystemExit("A transformed split lost activities.")
    models, metrics = fit_candidates(train_vectors, test_vectors)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_split(SPLIT_PATH, train_rows, test_rows)
    write_specification(FITTED_SPEC_PATH, preprocessing, test_unseen, len(train_rows), len(test_rows))
    write_metrics(METRICS_PATH, metrics)
    write_plot(PLOT_PATH, metrics)
    dump(
        {
            "preprocessing": preprocessing,
            "models": models,
            "train_activity_ids": [row["activity_id"] for row in train_rows],
            "test_activity_ids": [row["activity_id"] for row in test_rows],
        },
        MODEL_PATH,
    )
    print_report(
        json.loads(FITTED_SPEC_PATH.read_text(encoding="utf-8")),
        metrics,
    )


if __name__ == "__main__":
    main()
