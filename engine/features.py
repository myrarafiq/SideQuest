"""Feature definitions shared by every step (prepare, sweep, evaluate, recommend).

One vector per place, every value in [0, 1] before block weights:
  - category block: one-hot over the 12 activity categories      (weight w_cat)
  - price:          price_final / 4                               (weight 1)
  - vibe block:     8 flags; missing -> that category's training mean (weight 1)

Location and rating are deliberately NOT features: borough is a hard filter and rating is a
ranking bonus, so clusters describe the *kind of outing*, not where it is.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# The app package (export_for_app.py) points these at its own copies via environment variables.
DATA_PATH = Path(os.environ.get("SIDEQUEST_PLACES", REPO / "data" / "places_v1.parquet"))
OUTPUT = Path(os.environ.get("SIDEQUEST_MODEL_DIR", HERE / "output"))
SPEC_PATH = OUTPUT / "feature_spec.json"
SPLIT_PATH = OUTPUT / "split.csv"

CATEGORIES = [
    "Restaurants", "Cafes & Desserts", "Bars & Nightlife", "Parks & Outdoors", "Museums & Galleries",
    "Shows & Live Events", "Attractions & Tours", "Games & Indoor Fun", "Sports & Fitness",
    "Spas & Wellness", "Libraries & Bookstores", "Shopping",
]
VIBES = ["kids", "groups", "outdoor", "live_music", "dogs", "alcohol", "reservable", "open_late"]
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
MAX_PRICE = 4


def _flag(s: pd.Series) -> pd.Series:
    """Nullable boolean -> float 1/0/NaN."""
    return s.map({True: 1.0, False: 0.0}).astype(float)


def raw_vibes(df: pd.DataFrame) -> pd.DataFrame:
    """The 8 vibe flags as 1/0/NaN, before imputation."""
    alcohol_parts = pd.concat([_flag(df[c]) for c in ("serves_cocktails", "serves_beer", "serves_wine")], axis=1)
    alcohol = alcohol_parts.max(axis=1, skipna=True)          # any True -> 1; all NaN -> NaN
    outdoor = _flag(df["outdoor_seating"])
    outdoor = outdoor.where(df["activity_category"] != "Parks & Outdoors", 1.0)
    return pd.DataFrame({
        "kids": _flag(df["good_for_children"]),
        "groups": _flag(df["good_for_groups"]),
        "outdoor": outdoor,
        "live_music": _flag(df["live_music"]),
        "dogs": _flag(df["allows_dogs"]),
        "alcohol": alcohol,
        "reservable": _flag(df["reservable"]),
        "open_late": _flag(df["open_late"]),
    }, index=df.index)


def fit_imputation(train: pd.DataFrame) -> dict:
    """Per-category means of each vibe flag on the TRAINING rows (global mean as fallback)."""
    v = raw_vibes(train)
    v["activity_category"] = train["activity_category"].values
    global_mean = v[VIBES].mean().fillna(0.5)
    by_cat = {}
    for cat in CATEGORIES:
        m = v.loc[v["activity_category"] == cat, VIBES].mean()
        by_cat[cat] = {f: float(m[f]) if pd.notna(m[f]) else float(global_mean[f]) for f in VIBES}
    return {"by_category": by_cat, "global": {f: float(global_mean[f]) for f in VIBES}}


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


def feature_names() -> list[str]:
    return [f"cat:{c}" for c in CATEGORIES] + ["price"] + [f"vibe:{v}" for v in VIBES]


def transform(df: pd.DataFrame, spec: dict, w_cat: float) -> np.ndarray:
    """Places -> weighted feature matrix (n x 21)."""
    cats = np.zeros((len(df), len(CATEGORIES)))
    idx = df["activity_category"].map({c: i for i, c in enumerate(CATEGORIES)}).to_numpy()
    cats[np.arange(len(df)), idx] = 1.0
    price = (df["price_final"].astype(float).clip(0, MAX_PRICE) / MAX_PRICE).to_numpy()[:, None]
    v = raw_vibes(df)
    fill = pd.DataFrame([spec["imputation"]["by_category"][c] for c in df["activity_category"]], index=df.index)
    v = v.fillna(fill)[VIBES].to_numpy()
    return np.hstack([cats * w_cat, price, v])


def query_vector(categories: list[str], max_price: int, spec: dict, w_cat: float,
                 vibes: dict[str, float] | None = None) -> np.ndarray:
    """A user's preferences -> one vector in the same space as places.

    Selected categories share the one-hot weight. Price is the user's max price. Vibe flags are the
    user's toggles where given, otherwise the average profile of the selected categories (neutral).
    """
    if not categories:
        raise ValueError("Pick at least one category.")
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown categories: {unknown}")
    cats = np.zeros(len(CATEGORIES))
    for c in categories:
        cats[CATEGORIES.index(c)] = 1.0 / len(categories)
    price = np.array([min(max(max_price, 0), MAX_PRICE) / MAX_PRICE])
    neutral = {f: float(np.mean([spec["imputation"]["by_category"][c][f] for c in categories])) for f in VIBES}
    if vibes:
        neutral.update({k: float(v) for k, v in vibes.items() if k in VIBES})
    return np.hstack([cats * w_cat, price, [neutral[f] for f in VIBES]])


def load_places(fit_only: bool = False) -> pd.DataFrame:
    """Places from data/places_v1.parquet.

    fit_only=True  -> the 45,440 Google-verified places the model is fitted and evaluated on.
    fit_only=False -> the full recommendation catalog: those plus 755 official NYC Parks / GreenThumb places
                      (free, trustworthy, but no rating, hours or vibe data). They are never used to fit; they
                      are assigned to their nearest cluster like any new place.
    """
    df = pd.read_parquet(DATA_PATH)
    df = df[df["activity_category"].isin(CATEGORIES) & df["price_final"].notna()]
    if fit_only:
        df = df[df["verified_by"] == "google"]
    return df.reset_index(drop=True)
