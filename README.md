# Side Quest

One page: set up an outing (borough, group size, time), add what each person wants (budget, activities,
optional extras), and get **one deck of NYC places that fits the whole group**.

This repo holds the **app only**: the fitted model and the decision logic that turns inputs into a deck.
Fitting and evaluation live in the private [SideQuest-ML](https://github.com/SherryKhanW/SideQuest-ML) repo.
The product brief is in [docs/product_brief.md](docs/product_brief.md).

## Run it locally

You need **both repos cloned side by side** in the same folder, and Python 3.10+:

```
your-folder/
├── SideQuest/        <- this repo
└── SideQuest-ML/     <- private model repo (ask the CTO for access)
```

```bash
git clone https://github.com/SherryKhanW/SideQuest-ML.git
git clone https://github.com/myrarafiq/SideQuest.git
cd SideQuest
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5001.

If SideQuest-ML is somewhere else, copy `.env.example` to `.env` and set `SIDEQUEST_CATALOG` to the full path of
`SideQuest-ML/models/places_kmeans_v1/output/app/data/places_catalog.parquet`.

## What's here

| Path | What |
|---|---|
| `app.py` | Flask: `GET /` (the page), `GET /api/options` (form choices), `POST /api/recommend` (the deck) |
| `model/model_v1.json` | **Fitted model:** K-means with 25 centroids over category, price and 8 vibe features |
| `model/feature_spec.json`, `model/category_filters.json` | Feature order, the means used for missing values, and per-category card fields |
| `engine/` | **Decision logic:** `group.py` builds the shared deck (`recommend_room`); the others turn preferences into vectors and rank places |
| `templates/index.html`, `static/` | The page (HTML + JavaScript) |

`model/` and `engine/` are copied from `SideQuest-ML/models/places_kmeans_v1/output/app/` (made by
`export_for_app.py`). **Don't edit them here; change SideQuest-ML and re-copy.**

The place catalog (46,195 places, including Google Places content) is **not** in this repo. It's read from your
SideQuest-ML clone and is gitignored here.

## How a deck is made

1. **Room:** borough(s), group size and time.
2. **Each person:** max spend, activities, optional extras (kid-friendly, outdoors, late night & drinks) and wheelchair access.
3. **Hard limits** are never broken:
   - the chosen boroughs,
   - the **lowest** budget in the group,
   - open for at least 90 minutes from the chosen time,
   - an accessible entrance if anyone needs one.
4. The model finds the **clusters of similar places** that fit the whole group best: the average person plus the worst-off person. It ranks places by fit and rating, and fills the deck so **every person gets cards that suit them**.
5. Each card shows fields for its category (restaurants: cuisine, price range, hours, health grade; parks: type, size, nearest subway) and who it's good for.

## API

`POST /api/recommend`

```json
{"room": {"boroughs": ["Manhattan"], "group_size": 2, "when": "2026-12-04T20:00"},
 "members": [{"name": "Ana", "max_price": 3, "categories": ["Bars & Nightlife"], "toggles": ["nightlife"]},
             {"name": "Ben", "max_price": 2, "categories": ["Restaurants"], "needs_wheelchair": false}]}
```

`max_price` is 0 Free, 1 ≈ $20, 2 ≈ $30, 3 ≈ $90, 4 no limit. The response has `room_limits`, `deck` (10 cards:
`name`, `category`, `fields`, `for`, `maps_uri`), `cards_per_member` and `unserved_members`.
