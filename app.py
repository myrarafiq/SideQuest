"""SideQuest v1: one page that takes a group's inputs and shows the model's recommended deck.

The app holds only the fitted model (model/model_v1.json: k-means centroids) and the decision logic (engine/).
Fitting and evaluation live in the SideQuest-ML repo. The place catalog (Google Places content) is NOT in this
repo: it is read from your local SideQuest-ML clone; set SIDEQUEST_CATALOG in .env if it isn't in the default spot.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG = ROOT.parent / "SideQuest-ML" / "models" / "places_kmeans_v1" / "output" / "app" / "data" / "places_catalog.parquet"


def load_dotenv(path):
    """Load KEY=value pairs from a .env file without overriding existing vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")
CATALOG = Path(os.environ.get("SIDEQUEST_CATALOG", DEFAULT_CATALOG)).expanduser()
if not CATALOG.exists():
    sys.exit(f"Place catalog not found at {CATALOG}.\n"
             "Clone SideQuest-ML next to this repo, or set SIDEQUEST_CATALOG in .env (see README).")

# The engine reads these two settings when it is imported.
os.environ["SIDEQUEST_PLACES"] = str(CATALOG)
os.environ["SIDEQUEST_MODEL_DIR"] = str(ROOT / "model")
sys.path.insert(0, str(ROOT / "engine"))

from features import BOROUGHS, CATEGORIES  # noqa: E402
from group import GroupRecommender, Member, Room  # noqa: E402
from recommend import Recommender  # noqa: E402

engine = GroupRecommender(Recommender.load())   # loads the fitted model + catalog once (~1 s)

app = Flask(__name__)
app.json.sort_keys = False      # keep each card's fields in their per-category order
TOGGLES = ["kids", "outdoors", "nightlife"]


def parse_room(body):
    room = body.get("room") or {}
    boroughs = [b for b in room.get("boroughs") or [] if b in BOROUGHS]
    if not boroughs:
        raise ValueError("Pick at least one borough.")
    try:
        size = int(room.get("group_size"))
    except (TypeError, ValueError):
        raise ValueError("Group size must be a number.")
    if not 2 <= size <= 5:
        raise ValueError("Group size must be 2 to 5.")
    try:
        when = datetime.fromisoformat(str(room.get("when")))
    except ValueError:
        raise ValueError("Pick a date and time.")
    return Room(boroughs, size, when)


def parse_members(body, size):
    raw = body.get("members") or []
    if len(raw) != size:
        raise ValueError(f"Fill in preferences for all {size} people.")
    members = []
    for n, m in enumerate(raw, 1):
        name = " ".join(str(m.get("name") or f"Person {n}").split())[:40] or f"Person {n}"
        try:
            price = int(m.get("max_price"))
        except (TypeError, ValueError):
            raise ValueError(f"{name}: pick a max price.")
        if not 0 <= price <= 4:
            raise ValueError(f"{name}: max price must be 0 to 4.")
        cats = [c for c in m.get("categories") or [] if c in CATEGORIES]
        if not cats:
            raise ValueError(f"{name}: pick at least one activity.")
        toggles = [t for t in m.get("toggles") or [] if t in TOGGLES]
        members.append(Member(name, price, cats, toggles, needs_wheelchair=bool(m.get("needs_wheelchair"))))
    if len({m.name for m in members}) != len(members):
        raise ValueError("Give each person a different name.")
    return members


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/options")
def options():
    """What the form offers: the room settings and the v1 per-person settings."""
    return jsonify({"boroughs": BOROUGHS, "categories": CATEGORIES,
                    "prices": [{"value": 0, "label": "Free only"}, {"value": 1, "label": "Up to $ (about $10–20)"},
                               {"value": 2, "label": "Up to $$ (about $20–30)"},
                               {"value": 3, "label": "Up to $$$ (about $40–90)"},
                               {"value": 4, "label": "Any ($$$$ is $100+)"}],
                    "toggles": [{"id": "kids", "label": "Kid-friendly"}, {"id": "outdoors", "label": "Outdoors"},
                                {"id": "nightlife", "label": "Late night & drinks"}]})


@app.post("/api/recommend")
def recommend():
    body = request.get_json(silent=True) or {}
    try:
        room = parse_room(body)
        members = parse_members(body, room.group_size)
        result = engine.recommend_room(room, members)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))   # 5000 is taken by AirPlay on macOS
    app.run(host="127.0.0.1", port=port, debug=False)
