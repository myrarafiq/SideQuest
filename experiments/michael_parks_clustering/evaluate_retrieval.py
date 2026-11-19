#!/usr/bin/env python3
"""Compare baseline and k=4 retrieval on activity-derived held-out queries.

Each test activity supplies its categories and coordinates as a proxy query.
The searchable catalog is the 293 training activities only.
"""

from __future__ import annotations

import csv
import json
import sys

from fit_clusters import OUTPUT_DIR
from retrieve import CATALOG_NOTE, TOP_N, load_catalog, search

QUERY_PATH_NAME = "retrieval_query_results.csv"
SUMMARY_PATH_NAME = "retrieval_summary.json"


def mean(values: list[float]) -> float:
    if not values:
        return float("nan")
    return sum(values) / len(values)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    catalog = load_catalog()
    if set(catalog["test_ids"]) & {row["activity_id"] for row in catalog["train_rows"]}:
        raise SystemExit("A test activity is in the searchable catalog.")

    rows = []
    for activity_id in catalog["test_ids"]:
        activity = catalog["activities"][activity_id]
        result = search(activity["categories"], activity["latitude"], activity["longitude"], catalog)
        baseline_ids = [hit["activity_id"] for hit in result["baseline"]["results"]]
        v1_ids = [hit["activity_id"] for hit in result["v1"]["results"]]
        if activity_id in baseline_ids or activity_id in v1_ids:
            raise SystemExit(f"Query activity {activity_id} was returned from the catalog.")
        rows.append(
            {
                "query_activity_id": activity_id,
                "query_title": activity["title"],
                "query_source": "activity_derived_not_observed_user_search",
                "unknown_labels": result["unknown_labels"],
                "has_unseen_category_label": bool(result["unknown_labels"]),
                "v1_cluster": result["v1"]["cluster"],
                "candidate_pool_size": result["v1"]["candidate_pool_size"],
                "baseline_top5_ids": baseline_ids,
                "v1_top5_ids": v1_ids,
                "top5_overlap": result["top5_overlap"],
                "recall_against_exhaustive_retrieval": result["recall_against_exhaustive_retrieval"],
                "baseline_distance_calculations": result["baseline"]["distance_calculations"],
                "v1_centroid_comparisons": result["v1"]["centroid_comparisons"],
                "v1_distance_calculations": result["v1"]["distance_calculations"],
            }
        )

    query_path = OUTPUT_DIR / QUERY_PATH_NAME
    with query_path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "query_activity_id",
            "query_title",
            "query_source",
            "unknown_labels_json",
            "has_unseen_category_label",
            "v1_cluster",
            "candidate_pool_size",
            "baseline_top5_ids",
            "v1_top5_ids",
            "top5_overlap",
            "recall_against_exhaustive_retrieval",
            "baseline_distance_calculations",
            "v1_centroid_comparisons",
            "v1_distance_calculations",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "query_activity_id": row["query_activity_id"],
                    "query_title": row["query_title"],
                    "query_source": row["query_source"],
                    "unknown_labels_json": json.dumps(row["unknown_labels"], ensure_ascii=False),
                    "has_unseen_category_label": "true" if row["has_unseen_category_label"] else "false",
                    "v1_cluster": row["v1_cluster"],
                    "candidate_pool_size": row["candidate_pool_size"],
                    "baseline_top5_ids": "|".join(row["baseline_top5_ids"]),
                    "v1_top5_ids": "|".join(row["v1_top5_ids"]),
                    "top5_overlap": row["top5_overlap"],
                    "recall_against_exhaustive_retrieval": f"{row['recall_against_exhaustive_retrieval']:.1f}",
                    "baseline_distance_calculations": row["baseline_distance_calculations"],
                    "v1_centroid_comparisons": row["v1_centroid_comparisons"],
                    "v1_distance_calculations": row["v1_distance_calculations"],
                }
            )

    recalls = [row["recall_against_exhaustive_retrieval"] for row in rows]
    pools = [row["candidate_pool_size"] for row in rows]
    v1_calcs = [row["v1_distance_calculations"] for row in rows]
    baseline_calcs = rows[0]["baseline_distance_calculations"]
    unseen_rows = [row for row in rows if row["has_unseen_category_label"]]
    average_v1_calcs = mean(v1_calcs)
    summary = {
        "catalog_note": CATALOG_NOTE,
        "query_note": (
            "Each of the 126 test activities supplies its own categories and coordinates. "
            "These are activity-derived queries, not observed user searches. "
            "Recall against exhaustive retrieval is top-5 overlap divided by 5. "
            "It is not user satisfaction or recommendation accuracy."
        ),
        "catalog_size": 293,
        "query_count": len(rows),
        "top_n": TOP_N,
        "average_candidate_pool_size": mean(pools),
        "average_baseline_distance_calculations": baseline_calcs,
        "average_v1_distance_calculations": average_v1_calcs,
        "percentage_reduction_in_distance_calculations": 100.0 * (baseline_calcs - average_v1_calcs) / baseline_calcs,
        "mean_top5_recall_against_exhaustive_retrieval": mean(recalls),
        "queries_with_less_than_full_recall": sum(1 for value in recalls if value < 1.0),
        "unseen_category_queries": {
            "query_count": len(unseen_rows),
            "mean_top5_recall_against_exhaustive_retrieval": mean(
                [row["recall_against_exhaustive_retrieval"] for row in unseen_rows]
            ),
            "queries_with_less_than_full_recall": sum(
                1 for row in unseen_rows if row["recall_against_exhaustive_retrieval"] < 1.0
            ),
        },
    }
    summary_path = OUTPUT_DIR / SUMMARY_PATH_NAME
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"queries={summary['query_count']}")
    print(f"average_candidate_pool_size={summary['average_candidate_pool_size']:.6f}")
    print(f"average_v1_distance_calculations={summary['average_v1_distance_calculations']:.6f}")
    print(f"percentage_reduction_in_distance_calculations={summary['percentage_reduction_in_distance_calculations']:.6f}")
    print(f"mean_top5_recall={summary['mean_top5_recall_against_exhaustive_retrieval']:.6f}")
    print(f"queries_with_less_than_full_recall={summary['queries_with_less_than_full_recall']}")
    unseen = summary["unseen_category_queries"]
    print(
        "unseen_queries="
        f"{unseen['query_count']} mean_recall={unseen['mean_top5_recall_against_exhaustive_retrieval']:.6f} "
        f"below_full={unseen['queries_with_less_than_full_recall']}"
    )
    print(f"wrote {query_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
