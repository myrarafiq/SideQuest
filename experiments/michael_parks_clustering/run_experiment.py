#!/usr/bin/env python3
"""Reproduce the local Parks clustering experiment from the source JSON.

Run with the interpreter that has this folder's dependencies. Paths are based
on this file, not the shell's current directory. Modeling stays in the
existing preparation, fitting, retrieval, and evaluation modules.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import evaluate_retrieval
import fit_clusters
import prepare_activities
import retrieve

SOURCE_PATH = prepare_activities.SOURCE_PATH.resolve()
OUTPUT_DIR = fit_clusters.OUTPUT_DIR.resolve()
PROXY_NOTE = (
    "The percentage reduction in distance calculations is a computational proxy: "
    "it counts feature-space distance calculations, with 293 for the exhaustive pool "
    "and 4 centroid comparisons plus the selected cluster size for k=4. "
    "It is not measured latency, money saved, user satisfaction, or performance on observed user queries."
)


def print_summary() -> None:
    preparation = json.loads((OUTPUT_DIR / "preparation_summary.json").read_text(encoding="utf-8"))
    metrics = list(csv.DictReader((OUTPUT_DIR / "fit_metrics.csv").open(encoding="utf-8")))
    split_counts = Counter(
        row["split"] for row in csv.DictReader((OUTPUT_DIR / "data_split.csv").open(encoding="utf-8"))
    )
    example = json.loads((OUTPUT_DIR / "example_search.json").read_text(encoding="utf-8"))
    retrieval = json.loads((OUTPUT_DIR / "retrieval_summary.json").read_text(encoding="utf-8"))
    by_k = {int(row["k"]): row for row in metrics}
    print("REPRODUCTION SUMMARY")
    print(f"interpreter={sys.executable}")
    print(f"source={SOURCE_PATH}")
    print(f"output={OUTPUT_DIR}")
    print(
        "preparation "
        f"sessions={preparation['source_session_count']} "
        f"activities={preparation['activity_count']} "
        f"model_ready={preparation['model_ready_activity_count']} "
        f"excluded={preparation['excluded_activity_count']}"
    )
    print(f"split train={split_counts['train']} test={split_counts['test']}")
    print("sse k,train_total,test_total,train_per_activity,test_per_activity")
    for k in range(1, 9):
        row = by_k[k]
        print(
            f"{k},{row['train_total_sse']},{row['test_total_sse']},"
            f"{row['train_sse_per_activity']},{row['test_sse_per_activity']}"
        )
    one = by_k[1]
    four = by_k[4]
    print(
        "k4_versus_k1 "
        f"train_total {four['train_total_sse']} versus {one['train_total_sse']}; "
        f"test_total {four['test_total_sse']} versus {one['test_total_sse']}; "
        f"train_per_activity {four['train_sse_per_activity']} versus {one['train_sse_per_activity']}; "
        f"test_per_activity {four['test_sse_per_activity']} versus {one['test_sse_per_activity']}"
    )
    print(
        "hypothetical_query "
        f"cluster={example['v1']['cluster']} "
        f"pool={example['v1']['candidate_pool_size']} "
        f"unknown_labels={example['unknown_labels']}"
    )
    for method in ("baseline", "v1"):
        ids = [hit["activity_id"] for hit in example[method]["results"]]
        print(f"hypothetical_{method}_top5={','.join(ids)}")
    unseen = retrieval["unseen_category_queries"]
    print(
        "retrieval "
        f"mean_pool={retrieval['average_candidate_pool_size']} "
        f"baseline_calculations={retrieval['average_baseline_distance_calculations']} "
        f"v1_calculations={retrieval['average_v1_distance_calculations']} "
        f"calculation_reduction_percent={retrieval['percentage_reduction_in_distance_calculations']} "
        f"mean_top5_recall={retrieval['mean_top5_recall_against_exhaustive_retrieval']} "
        f"below_full_recall={retrieval['queries_with_less_than_full_recall']} "
        f"unseen_queries={unseen['query_count']} "
        f"unseen_mean_recall={unseen['mean_top5_recall_against_exhaustive_retrieval']}"
    )
    print(PROXY_NOTE)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if not SOURCE_PATH.is_file():
        raise SystemExit(f"Missing source file: {SOURCE_PATH}")
    prepare_activities.main()
    fit_clusters.main()
    retrieve.main()
    evaluate_retrieval.main()
    print_summary()


if __name__ == "__main__":
    main()
