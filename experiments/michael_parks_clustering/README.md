# NYC Parks activity clustering

Local experiment on one NYC Parks file. It prepares activities, fits K-means for k=1 through 8, and runs a k=4 retrieval comparison. It does not call an API or a database.

## Reproduce

From the repository root, with this folder's dependencies installed:

```bash
python -m venv experiments/michael_parks_clustering/.venv
experiments/michael_parks_clustering/.venv/Scripts/python.exe -m pip install -r experiments/michael_parks_clustering/requirements.txt
experiments/michael_parks_clustering/.venv/Scripts/python.exe experiments/michael_parks_clustering/run_experiment.py
```

`run_experiment.py` uses the interpreter that launched it and resolves paths from the repository layout. It calls `prepare_activities.py`, `fit_clusters.py`, `retrieve.py`, and `evaluate_retrieval.py` in that order. The source file is `data/nyc_parks/latest/events.json`. Outputs are written to `experiments/michael_parks_clustering/output/`.

## Data

The file is NYC Open Data dataset `w3wp-dpdi`, NYC Parks Public Events: Upcoming 14 Days, collected at `2026-10-13T22:48:41.550913-04:00`. It contains 882 scheduled sessions with starts from 2026-10-13 through 2026-10-27. This is one rolling window, not a historical archive. There is no price field and no user record.

One source row is one scheduled session. One activity is one normalized title at one normalized location. Normalization is Unicode NFKC, case-folding, and replacement of punctuation with spaces. The same title at a different location stays a different activity. On this file that rule produces 433 activities from 882 sessions, and the normalized key matches the raw title-location pair. Sessions are combined only when their descriptions match after whitespace and case folding and their category sets are nested. Forest Fitness at Margaret Corbin Circle is the one nested label mismatch; its seven sessions stay one activity and use the union of the labels.

Fourteen activities are excluded from model fitting and from the searchable catalog. Their sessions remain in `output/session_mapping.csv`.

| Reason | Activities |
| --- | ---: |
| Location text contains virtual or online | 9 |
| No single measured coordinate point | 3 |
| No category labels | 2 |

Eligible activities: 419. The fixed split is `train_test_split` on activity ids sorted lexicographically, `test_size=0.3`, `shuffle=True`, `random_state=42`: 293 training and 126 test.

## Features

Preparation proposes a representation for all 419 eligible activities and saves it in `output/model_specification.json` and `output/feature_matrix.csv`. Fitting does not train on that full-data matrix.

The training fit builds the same representation from the 293 training activities only:

- Categories are raw multi-hot 0/1 columns. The vocabulary is the sorted training labels. Columns are not ordinal ids and are not standardized.
- Coordinates use the equirectangular projection with Earth radius 6371 km. The origin is the coordinate-wise median of the training activities.
- One geographic multiplier is applied to both projected axes: the square root of the summed training category-column population variances divided by the summed training coordinate population variances.
- Test rows use that saved vocabulary, origin, and multiplier. Labels absent from the training vocabulary are reported and omitted. They do not add columns, and the test activity is not dropped.

## k=4

The fit writes a model for every k from 1 through 8 (`random_state=42`, `n_init=10`). No elbow rule selects k. Total SSE and SSE per activity decline through k=8 on both splits.

k=4 is the designated local v1 candidate because that saved model is the one used by the retrieval rule. On this split its training total SSE is 1026.3787662367 and its test total SSE is 437.9343342840. The k=1 model, one center for all training activities, has training total SSE 1765.8839590444 and test total SSE 802.0059343952. Per activity, k=4 is 3.5029992022 training and 3.4756693197 test, against 6.0269077100 and 6.3651264635 for k=1. That comparison describes these two fits. It is not an automatic selection rule.

## Decision rule

The catalog is the 293 training activities from the October 13 collection. A query is a list of category labels plus a latitude and longitude. It is transformed with the training-fitted preprocessing.

- Baseline: rank all 293 training activities by Euclidean distance in that feature space and return 5. This uses 293 distance calculations.
- V1: assign the query to the nearest saved k=4 center, then return the 5 nearest training activities inside that cluster. This uses 4 centroid comparisons plus the selected cluster's training count.
- Equal distances keep the lexicographically smaller activity id. Equal centroid distances keep the smaller cluster id.

The hypothetical demonstration query is `categories=["Fitness", "Exercise Classes"]`, latitude `40.73`, longitude `-73.94`. It is not an observed user search, and the returned titles are rows in the October catalog, not events confirmed to be available now.

Held-out evaluation turns each of the 126 test activities into a proxy query from its own categories and coordinates. Those queries are activity-derived. Test activities are not added to the catalog. Top-5 recall is the size of the id overlap between the two five-result lists, divided by 5.

The reduction in distance calculations is a computational proxy for doing less of that arithmetic than the exhaustive pool. It is not measured latency, money saved, user satisfaction, or performance on observed user queries.

## Limitations

- The source is one 14-day Parks window collected on 2026-10-13.
- Confirmed price, travel time, availability, and user preferences are not in the file and are not inferred.
- Recall measures agreement with exhaustive retrieval in this feature space. It does not measure whether a person would accept the result.
- Seven test labels never appear in training. Those query labels are omitted from the vector.
- k=4 is a designated candidate. The SSE curves do not stop at k=4.
- The full-data multiplier in `output/model_specification.json` is not the multiplier used to fit or retrieve.
