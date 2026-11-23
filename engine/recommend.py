#!/usr/bin/env python3
"""Decision logic: user preferences -> nearest cluster -> filtered, ranked, diversified deck.

    python recommend.py --borough Brooklyn --max-price 2 --categories "Restaurants"
    python recommend.py --borough any --max-price 3 --categories "Bars & Nightlife" --nightlife

For each selected category:
  1. Build the query vector in the same feature space as places (features.query_vector).
  2. Compare it with the centroids using only what the user expressed: the category block, price, and any
     vibe toggles they switched on. Vibes the user said nothing about don't pull the query anywhere.
  3. Hard filters: borough (or "any"), price_final <= max_price, the category. A place that fails a hard
     filter is never returned.
  4. Take places from the nearest cluster (plus any cluster within CLUSTER_TIE_BAND of it); if fewer than
     DECK_SIZE pass the filters, add the next-nearest.
  5. Rank by the same masked distance minus a quality bonus (Bayesian-smoothed Google rating).
  6. Diversify: at most MAX_PER_SUBCATEGORY cards per subcategory, one card per place name.
Multi-category queries interleave the per-category decks so every chosen category shows up.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from features import BOROUGHS, CATEGORIES, OUTPUT, VIBES, load_places, load_spec, query_vector, transform

MODEL_PATH = OUTPUT / "model_v1.json"
DECK_SIZE = 10
MAX_PER_SUBCATEGORY = 3
RATING_PRIOR_COUNT = 50          # Bayesian smoothing: a 5.0 from 3 ratings is pulled toward the mean
QUALITY_WEIGHT = 0.5             # how much rating quality counts against feature-space distance
CLUSTER_TIE_BAND = 0.05          # clusters this close to the nearest one are treated as equally near
VIBE_TOGGLES = {                 # optional user toggles -> vibe flags
    "kids": {"kids": 1.0},
    "outdoors": {"outdoor": 1.0},
    "nightlife": {"open_late": 1.0, "alcohol": 1.0},
    "dogs": {"dogs": 1.0},
    "groups": {"groups": 1.0},
    "live_music": {"live_music": 1.0},
}
PRICE_LABEL = {0: "Free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}


# ---------------------------------------------------------------- shared helpers (also used by evaluate.py)
def expressed_mask(vibes: dict[str, float] | None) -> np.ndarray:
    """Feature dims the user expressed: all category dims, price, and toggled vibe flags."""
    return np.array([True] * len(CATEGORIES) + [True] + [v in (vibes or {}) for v in VIBES])


def centroid_distances(q: np.ndarray, centers: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    m = np.ones(len(q), dtype=bool) if mask is None else mask
    return np.sqrt(((centers[:, m] - q[m]) ** 2).sum(axis=1))


def nearest_order(q: np.ndarray, centers: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Cluster ids ordered by (masked) distance from q; ties -> smaller id."""
    d = centroid_distances(q, centers, mask)
    return np.lexsort((np.arange(len(centers)), d))


def assign(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    d2 = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return d2.argmin(axis=1)


def hard_filter(df: pd.DataFrame, borough: str, max_price: int, categories: list[str]) -> np.ndarray:
    m = df["activity_category"].isin(categories).to_numpy() & (df["price_final"].to_numpy() <= max_price)
    if borough != "any":
        m &= (df["borough"] == borough).to_numpy()
    return m


def quality(df: pd.DataFrame, prior_mean: float) -> np.ndarray:
    """Bayesian-smoothed rating scaled to ~[0, 1] (3.5 -> 0, 5.0 -> 1). Unrated places get the prior."""
    r = df["rating"].fillna(prior_mean).to_numpy()
    n = df["rating_count"].fillna(0).to_numpy()
    bayes = (RATING_PRIOR_COUNT * prior_mean + r * n) / (RATING_PRIOR_COUNT + n)
    return np.clip((bayes - 3.5) / 1.5, 0, 1)


def rank(X: np.ndarray, q: np.ndarray, mask: np.ndarray, qual: np.ndarray, idx: np.ndarray,
         ids: np.ndarray) -> np.ndarray:
    """Candidate indexes ordered best-first: masked distance minus quality bonus; ties -> smaller id."""
    if len(idx) == 0:
        return idx
    dist = np.sqrt(((X[idx][:, mask] - q[mask]) ** 2).sum(axis=1))
    score = dist - QUALITY_WEIGHT * qual[idx]
    return idx[np.lexsort((ids[idx], score))]


def cluster_pool(labels: np.ndarray, ok: np.ndarray, dists: np.ndarray, n: int) -> tuple[np.ndarray, list[int]]:
    """Places passing the filters from the nearest cluster(s).

    Every cluster within CLUSTER_TIE_BAND of the nearest counts as equally near and is always included;
    further clusters are added in distance order only until >= n places pass the filters.
    """
    order = np.lexsort((np.arange(len(dists)), dists))
    pool, used = np.zeros(len(labels), dtype=bool), []
    for c in order:
        if used and dists[c] > dists[order[0]] + CLUSTER_TIE_BAND and pool.sum() >= n:
            break
        used.append(int(c))
        pool |= ok & (labels == c)
    return pool, used


def place_type(p: pd.Series) -> str:
    """Display type: Google's label, else its type id, else the activity category (116 places have no type)."""
    for col in ("subcategory_label", "subcategory", "activity_category"):
        if pd.notna(p[col]):
            return str(p[col])
    return ""


# ---------------------------------------------------------------- model
@dataclass
class Recommender:
    centers: np.ndarray
    w_cat: float
    names: list[str]
    spec: dict
    places: pd.DataFrame
    X: np.ndarray
    labels: np.ndarray
    qual: np.ndarray

    @classmethod
    def load(cls, model_path=MODEL_PATH, places: pd.DataFrame | None = None) -> "Recommender":
        model = json.loads(model_path.read_text())
        spec = load_spec()
        places = load_places() if places is None else places
        centers = np.asarray(model["centroids"], dtype=float)
        X = transform(places, spec, model["w_cat"])
        return cls(centers, model["w_cat"], [c["name"] for c in model["clusters"]], spec, places, X,
                   assign(X, centers), quality(places, float(places["rating"].mean())))

    def _category_deck(self, cat: str, borough: str, max_price: int, vibes: dict, mask: np.ndarray, n: int):
        q = query_vector([cat], max_price, self.spec, self.w_cat, vibes)
        dists = centroid_distances(q, self.centers, mask)
        ok = hard_filter(self.places, borough, max_price, [cat])
        pool, used = cluster_pool(self.labels, ok, dists, n)
        ranked = rank(self.X, q, mask, self.qual, np.flatnonzero(pool), self.places["master_id"].to_numpy())
        deck, per_sub, names = [], {}, set()
        for i in ranked:
            sub, name = self.places.at[i, "subcategory"], self.places.at[i, "name"].strip().lower()
            if name in names:                   # one card per name: no three branches of the same chain
                continue
            if per_sub.get(sub, 0) < MAX_PER_SUBCATEGORY:
                per_sub[sub] = per_sub.get(sub, 0) + 1
                names.add(name)
                deck.append(int(i))
            if len(deck) == n:
                break
        if len(deck) < n:                       # small pool: top up in rank order past the diversity cap
            for i in ranked:
                name = self.places.at[i, "name"].strip().lower()
                if int(i) not in deck and name not in names:
                    deck.append(int(i))
                    names.add(name)
                if len(deck) == n:
                    break
        return deck, used, int(np.argmin(dists)), int(ok.sum())

    def recommend(self, borough: str, max_price: int, categories: list[str],
                  toggles: list[str] | None = None, n: int = DECK_SIZE) -> dict:
        if borough != "any" and borough not in BOROUGHS:
            raise ValueError(f"borough must be one of {BOROUGHS} or 'any'")
        unknown = [t for t in toggles or [] if t not in VIBE_TOGGLES]
        if unknown:
            raise ValueError(f"unknown toggles {unknown}; choose from {list(VIBE_TOGGLES)}")
        vibes = {}
        for t in toggles or []:
            vibes.update(VIBE_TOGGLES[t])
        mask = expressed_mask(vibes)

        per_cat, used, nearest, matching = [], [], [], 0
        for cat in dict.fromkeys(categories):                      # unique, in the user's order
            deck, u, first, m = self._category_deck(cat, borough, max_price, vibes, mask, n)
            per_cat.append(deck)
            used += [c for c in u if c not in used]
            nearest.append(first)
            matching += m
        deck = []                                                  # interleave categories round-robin
        for i in range(n):
            for d in per_cat:
                if i < len(d) and len(deck) < n:
                    deck.append(d[i])

        ok_all = hard_filter(self.places, borough, max_price, categories)
        cards = []
        for i in deck:
            p = self.places.loc[i]
            cards.append({
                "master_id": p["master_id"], "verified_by": p["verified_by"],
                "name": p["name"], "category": p["activity_category"], "type": place_type(p),
                "borough": p["borough"], "neighborhood": p["neighborhood"],
                "price": PRICE_LABEL[int(p["price_final"])], "price_source": p["price_final_source"],
                "rating": None if pd.isna(p["rating"]) else float(p["rating"]),
                "rating_count": None if pd.isna(p["rating_count"]) else int(p["rating_count"]),
                "cluster": int(self.labels[i]), "cluster_name": self.names[int(self.labels[i])],
                "summary": p["generative_summary"], "maps_uri": p["maps_uri"],
                "passes_filters": bool(ok_all[i]),
            })
        return {
            "query": {"borough": borough, "max_price": max_price, "categories": categories, "toggles": toggles or []},
            "nearest_cluster": {"id": nearest[0], "name": self.names[nearest[0]]},
            "nearest_cluster_per_category": {c: {"id": k, "name": self.names[k]}
                                             for c, k in zip(dict.fromkeys(categories), nearest)},
            "clusters_used": [{"id": c, "name": self.names[c]} for c in used],
            "matching_places_in_catalog": matching,
            "deck": cards,
        }


def main() -> None:
    ap = argparse.ArgumentParser(description="Recommend a deck for one user's preferences.")
    ap.add_argument("--borough", default="any", help=f"one of {BOROUGHS} or 'any'")
    ap.add_argument("--max-price", type=int, required=True, help="0=free, 1=$, 2=$$, 3=$$$, 4=$$$$")
    ap.add_argument("--categories", required=True, help=f"comma-separated, from: {', '.join(CATEGORIES)}")
    for t in VIBE_TOGGLES:
        ap.add_argument(f"--{t.replace('_', '-')}", action="store_true")
    a = ap.parse_args()
    toggles = [t for t in VIBE_TOGGLES if getattr(a, t)]
    rec = Recommender.load()
    out = rec.recommend(a.borough, a.max_price, [c.strip() for c in a.categories.split(",")], toggles)
    for c, k in out["nearest_cluster_per_category"].items():
        print(f"{c}: nearest cluster {k['id']} - {k['name']}")
    print(f"clusters used: {[c['id'] for c in out['clusters_used']]}   matching places in catalog: "
          f"{out['matching_places_in_catalog']:,}\n")
    for n, c in enumerate(out["deck"], 1):
        rating = f"{c['rating']}★ ({c['rating_count']:,})" if c["rating"] else "unrated"
        print(f"{n:2d}. {c['name']}  ·  {c['type']}  ·  {c['price']}  ·  {rating}  ·  {c['neighborhood']}, {c['borough']}")


if __name__ == "__main__":
    main()
