#!/usr/bin/env python3
"""Per-category settings: which place types count, which filters to show, which fields a card shows.

Single source of truth for the decision logic (group.py) and for the app (output/category_filters.json).

  TYPE_GROUPS   curated, user-facing groups of Google types per category. A place whose type is in no
                group is NOT recommended (removes data noise like "Doctor" under Spas or "Supermarket" under
                Shopping). Places with no Google type at all (116) are kept as "Other".
  CUISINES      user-facing cuisine groups for restaurants.
  FILTERS       per category, the settings worth showing (from the coverage analysis in docs/USER_FILTERS.md).
                v1=True marks what the v1 app uses; the rest is the Phase B (v2) UI.
  CARD_FIELDS   per category, what a card shows.

    python category_config.py      # writes output/category_filters.json and prints coverage per category
"""
from __future__ import annotations

import json

import pandas as pd

from features import CATEGORIES, OUTPUT

TYPE_GROUPS: dict[str, dict[str, list[str]]] = {
    "Restaurants": {"Restaurants": []},          # every *_restaurant type + the list below (see RESTAURANT_TYPES)
    "Cafes & Desserts": {
        "Coffee & tea": ["coffee_shop", "cafe", "tea_house", "coffee_roastery", "coffee_stand", "juice_shop", "acai_shop"],
        "Bakeries & pastries": ["bakery", "pastry_shop", "cake_shop", "donut_shop", "bagel_shop"],
        "Ice cream & desserts": ["ice_cream_shop", "dessert_shop", "dessert_restaurant", "chocolate_shop", "candy_store",
                                 "confectionery", "chocolate_factory"],
    },
    "Bars & Nightlife": {
        "Bars": ["bar"],
        "Cocktail & wine bars": ["cocktail_bar", "wine_bar", "lounge_bar", "winery"],
        "Pubs & gastropubs": ["pub", "irish_pub", "gastropub"],
        "Sports bars": ["sports_bar"],
        "Clubs & hookah": ["night_club", "hookah_bar"],
        "Karaoke": ["karaoke"],
        "Breweries & beer gardens": ["brewery", "brewpub", "beer_garden"],
    },
    "Parks & Outdoors": {
        "Parks": ["park", "city_park", "neighborhood_park", "community_park", "flagship_park", "state_park",
                  "managed_sites", "memorial_park", "picnic_ground", "barbecue_area"],
        "Playgrounds": ["playground", "jointly_operated_playground"],
        "Gardens": ["garden", "community_garden", "botanical_garden"],
        "Dog parks": ["dog_park"],
        "Nature & hiking": ["nature_preserve", "nature_area", "hiking_area", "wildlife_refuge", "scenic_spot"],
        "Beaches & waterfront": ["beach", "waterfront_facility", "fishing_pier", "marina"],
        "Plazas": ["triangle_or_plaza", "plaza"],
        "Skateparks": ["skateboard_park"],
    },
    "Museums & Galleries": {
        "Museums": ["museum", "history_museum", "planetarium", "cultural_center"],
        "Art museums": ["art_museum"],
        "Galleries & studios": ["art_gallery", "art_studio"],
    },
    "Shows & Live Events": {
        "Theater": ["performing_arts_theater", "opera_house"],
        "Live music & concerts": ["live_music_venue", "concert_hall", "amphitheatre"],
        "Comedy": ["comedy_club"],
        "Movies": ["movie_theater"],
        "Stadiums & arenas": ["stadium", "arena"],
        "Event venues": ["event_venue"],
    },
    "Attractions & Tours": {
        "Sights": ["tourist_attraction"],
        "Landmarks & monuments": ["historical_landmark", "historical_place", "monument", "landmark", "cultural_landmark",
                                  "castle", "fountain", "sculpture", "bridge", "historic_house_park"],
        "Zoos & aquariums": ["zoo", "aquarium", "wildlife_park"],
        "Observation decks": ["observation_deck"],
        "Amusement parks": ["amusement_park", "roller_coaster"],
        "Tours": ["tour_agency", "visitor_center"],
    },
    "Games & Indoor Fun": {
        "Arcades & amusement": ["amusement_center", "video_arcade", "adventure_sports_center", "paintball_center",
                                "go_karting_venue"],
        "Bowling": ["bowling_alley"],
        "Indoor play (kids)": ["indoor_playground"],
        "Ice skating": ["ice_skating_rink"],
        "Mini golf & indoor golf": ["miniature_golf_course", "indoor_golf_course"],
    },
    "Sports & Fitness": {
        "Gyms": ["gym", "fitness_center"],
        "Yoga & pilates": ["yoga_studio"],
        "Pools": ["swimming_pool"],
        "Fields, courts & rec centers": ["recreational_field_or_courts", "athletic_field", "sports_complex",
                                         "sports_activity_location", "tennis_court", "sports_club",
                                         "buildings_or_institutions", "community_center"],
        "Classes & coaching": ["sports_school", "sports_coaching"],
    },
    "Spas & Wellness": {
        "Spas & saunas": ["spa", "wellness_center", "sauna"],
        "Massage": ["massage_spa", "massage"],
        "Beauty & nails": ["beauty_salon", "nail_salon"],
    },
    "Libraries & Bookstores": {
        "Libraries": ["library"],
        "Bookstores": ["book_store"],
    },
    "Shopping": {
        "Markets": ["market", "farmers_market", "flea_market"],
        "Malls & department stores": ["shopping_mall", "department_store"],
        "Thrift & vintage": ["thrift_store"],
        "Gifts & toys": ["gift_shop", "toy_store"],
        "Clothing & jewelry": ["clothing_store", "womens_clothing_store", "shoe_store", "jewelry_store"],
        "Flowers & home": ["florist", "home_goods_store", "garden_center"],
    },
}
RESTAURANT_TYPES = {"restaurant", "deli", "diner", "sandwich_shop", "bar_and_grill", "steak_house", "salad_shop",
                    "bistro", "food_court", "noodle_shop", "hot_dog_stand", "kebab_shop", "cafeteria", "snack_bar",
                    "meal_takeaway"}

CUISINES: dict[str, list[str]] = {
    "Chinese": ["chinese", "cantonese", "dim sum", "dumpling", "chinese noodle", "hot pot", "taiwanese", "szechuan", "shanghainese"],
    "Pizza & Italian": ["pizza", "italian"],
    "Mexican & Latin": ["mexican", "taco", "tex mex", "latin american", "dominican", "colombian", "peruvian", "ecuadorian",
                        "salvadoran", "cuban", "venezuelan", "argentinian", "brazilian", "guatemalan", "puerto rican"],
    "American & burgers": ["american", "hamburger", "burger", "chicken", "chicken wings", "soul food", "barbecue",
                           "hot dog", "family", "southern", "cajun"],
    "Japanese & sushi": ["japanese", "sushi", "ramen", "japanese izakaya", "yakitori"],
    "Korean": ["korean", "korean barbecue"],
    "Southeast Asian": ["thai", "vietnamese", "filipino", "malaysian", "indonesian", "burmese", "cambodian"],
    "Indian & South Asian": ["indian", "bangladeshi", "pakistani", "nepalese", "tibetan", "sri lankan"],
    "Middle Eastern & Mediterranean": ["mediterranean", "middle eastern", "greek", "turkish", "lebanese", "israeli",
                                       "gyro", "falafel", "shawarma", "halal", "persian", "afghani"],
    "Caribbean & African": ["caribbean", "jamaican", "haitian", "african", "ethiopian", "west african"],
    "European": ["french", "spanish", "german", "irish", "polish", "eastern european", "uzbek", "russian",
                 "georgian", "british"],
    "Seafood": ["seafood"],
    "Vegan & healthy": ["vegan", "vegetarian", "health food"],
    "Breakfast & brunch": ["breakfast", "brunch", "breakfast and brunch"],
    "Kosher": ["kosher"],
    "Steak & fine dining": ["fine dining"],
    "Asian fusion": ["asian", "asian fusion", "fusion"],
}
CUISINE_BY_TYPE = {"sandwich_shop": "Sandwiches & delis", "deli": "Sandwiches & delis", "diner": "American & burgers",
                   "bar_and_grill": "American & burgers", "steak_house": "Steak & fine dining",
                   "salad_shop": "Vegan & healthy", "noodle_shop": "Asian fusion", "hot_dog_stand": "American & burgers",
                   "kebab_shop": "Middle Eastern & Mediterranean", "fast_food_restaurant": "Fast food"}

# Universal settings every member sees. kind: price | toggle | min_rating ; hard: never violated when set.
UNIVERSAL = [
    {"id": "max_price", "label": "Max spend per person", "kind": "price", "hard": True, "v1": True,
     "options": [{"value": 0, "label": "Free"}, {"value": 1, "label": "Up to ~$20"}, {"value": 2, "label": "Up to ~$30"},
                 {"value": 3, "label": "Up to ~$90"}, {"value": 4, "label": "No limit"}]},
    {"id": "kids", "label": "Kid-friendly", "kind": "toggle", "hard": False, "v1": True},
    {"id": "outdoors", "label": "Outdoors", "kind": "toggle", "hard": False, "v1": True},
    {"id": "nightlife", "label": "Late night & drinks", "kind": "toggle", "hard": False, "v1": True},
    {"id": "needs_wheelchair", "label": "Wheelchair-accessible entrance", "kind": "toggle", "hard": True, "v1": True},
    {"id": "min_rating", "label": "Minimum rating", "kind": "min_rating", "hard": False, "v1": False,
     "options": [4.0, 4.3, 4.5, 4.7]},
]
# Category-specific extras (Phase B UI). field = data column; True-valued place flag means it matches.
EXTRA = {
    "Restaurants": [("cuisine", "Cuisine", "multi", None), ("outdoor_seating", "Outdoor seating", "toggle", "outdoor_seating"),
                    ("live_music", "Live music", "toggle", "live_music"), ("kids_menu", "Kids' menu", "toggle", "menu_for_children"),
                    ("reservable", "Takes reservations", "toggle", "reservable"), ("vegetarian", "Vegetarian options", "toggle", "serves_vegetarian"),
                    ("brunch", "Brunch", "toggle", "serves_brunch"), ("sports_tv", "Sports on TV", "toggle", "good_for_watching_sports"),
                    ("grade_a", "Health grade A", "toggle", "inspection_grade"), ("no_chains", "Skip chains", "toggle", "is_chain")],
    "Cafes & Desserts": [("type", "Type", "multi", None), ("outdoor_seating", "Outdoor seating", "toggle", "outdoor_seating")],
    "Bars & Nightlife": [("type", "Type", "multi", None), ("live_music", "Live music", "toggle", "live_music"),
                         ("sports_tv", "Sports on TV", "toggle", "good_for_watching_sports"),
                         ("outdoor_seating", "Outdoor seating", "toggle", "outdoor_seating"),
                         ("dogs", "Dog-friendly", "toggle", "allows_dogs"), ("reservable", "Takes reservations", "toggle", "reservable")],
    "Parks & Outdoors": [("type", "Type", "multi", None), ("dogs", "Dog-friendly", "toggle", "allows_dogs"),
                         ("big_parks", "Big parks (10+ acres)", "toggle", "acres")],
    "Museums & Galleries": [("type", "Type", "multi", None), ("famous", "Famous landmarks", "toggle", "wikidata_sitelinks")],
    "Shows & Live Events": [("type", "Type", "multi", None)],
    "Attractions & Tours": [("type", "Type", "multi", None), ("famous", "Famous landmarks", "toggle", "wikidata_sitelinks")],
    "Games & Indoor Fun": [("type", "Type", "multi", None)],
    "Sports & Fitness": [("type", "Type", "multi", None)],
    "Spas & Wellness": [("type", "Type", "multi", None)],
    "Libraries & Bookstores": [("type", "Type", "multi", None)],
    "Shopping": [("type", "Type", "multi", None)],
}
FREE_CATEGORIES = {"Parks & Outdoors"}      # price filter hidden; libraries are free via price_final = 0

CARD_FIELDS = {
    "Restaurants": ["cuisine", "price_range", "rating", "neighborhood", "open_until", "inspection_grade", "summary", "tags"],
    "Cafes & Desserts": ["type", "price_range", "rating", "neighborhood", "open_until", "summary", "tags"],
    "Bars & Nightlife": ["type", "price_range", "rating", "neighborhood", "open_until", "summary", "tags"],
    "Parks & Outdoors": ["type", "free", "size", "rating", "neighborhood", "nearest_subway", "official_label"],
    "Museums & Galleries": ["type", "price_note", "rating", "famous", "neighborhood", "open_until", "summary"],
    "Shows & Live Events": ["type", "price_note", "rating", "neighborhood", "venue_note", "summary"],
    "Attractions & Tours": ["type", "price_note", "rating", "famous", "neighborhood", "open_until", "summary"],
    "Games & Indoor Fun": ["type", "price_note", "rating", "neighborhood", "open_until", "summary"],
    "Sports & Fitness": ["type", "price_note", "rating", "neighborhood", "open_until"],
    "Spas & Wellness": ["type", "price_note", "rating", "neighborhood", "open_until"],
    "Libraries & Bookstores": ["type", "free_if_library", "rating", "neighborhood", "open_until"],
    "Shopping": ["type", "rating", "neighborhood", "open_until"],
}

_TYPE_TO_GROUP = {(cat, t): g for cat, groups in TYPE_GROUPS.items() for g, ts in groups.items() for t in ts}
_CUISINE_TO_GROUP = {c: g for g, cs in CUISINES.items() for c in cs}


def type_group(category: str, subcategory) -> str | None:
    """User-facing type group, or None if the place should never be recommended (data noise)."""
    if subcategory is None or (isinstance(subcategory, float) and pd.isna(subcategory)):
        return "Other"
    if category == "Restaurants":
        return "Restaurants" if subcategory.endswith("_restaurant") or subcategory in RESTAURANT_TYPES else None
    return _TYPE_TO_GROUP.get((category, subcategory))


def cuisine_group(cuisine, subcategory) -> str | None:
    if isinstance(cuisine, str) and cuisine in _CUISINE_TO_GROUP:
        return _CUISINE_TO_GROUP[cuisine]
    if isinstance(subcategory, str) and subcategory in CUISINE_BY_TYPE:
        return CUISINE_BY_TYPE[subcategory]
    return None


def annotate(places: pd.DataFrame) -> pd.DataFrame:
    """Add type_group and cuisine_group columns (None type_group = excluded noise)."""
    out = places.copy()
    out["type_group"] = [type_group(c, s) for c, s in zip(out["activity_category"], out["subcategory"])]
    out["cuisine_group"] = [cuisine_group(c, s) if cat == "Restaurants" else None
                            for c, s, cat in zip(out["cuisine"], out["subcategory"], out["activity_category"])]
    return out


def build_config(places: pd.DataFrame) -> dict:
    p = annotate(places)
    cats = {}
    for cat in CATEGORIES:
        sub = p[p["activity_category"] == cat]
        kept = sub[sub["type_group"].notna()]
        filters = [f for f in UNIVERSAL if not (cat in FREE_CATEGORIES and f["id"] == "max_price")]
        extras = []
        for fid, label, kind, field in EXTRA[cat]:
            f = {"id": fid, "label": label, "kind": kind, "hard": False, "v1": False}
            if fid == "type":
                f["options"] = [g for g in TYPE_GROUPS[cat] if (kept["type_group"] == g).any()]
            elif fid == "cuisine":
                f["options"] = [g for g in list(CUISINES) + ["Sandwiches & delis", "Fast food"]
                                if (kept["cuisine_group"] == g).any()]
            if field:
                f["coverage"] = round(float(kept[field].notna().mean()), 3)
            extras.append(f)
        cats[cat] = {
            "places": int(len(kept)), "excluded_noise": int(len(sub) - len(kept)),
            "type_groups": {g: int((kept["type_group"] == g).sum()) for g in list(TYPE_GROUPS[cat]) + ["Other"]
                            if (kept["type_group"] == g).any()},
            "filters": filters + extras,
            "card_fields": CARD_FIELDS[cat],
            "price_is_estimated": bool((kept["price_final_source"] == "category_estimate").mean() > 0.5),
        }
    return {"room_settings": [
                {"id": "boroughs", "label": "Borough(s)", "kind": "multi", "hard": True,
                 "options": ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]},
                {"id": "group_size", "label": "How many people", "kind": "number", "min": 2, "max": 5},
                {"id": "when", "label": "When", "kind": "datetime", "hard": True,
                 "note": "places known to be closed then are never shown; unknown hours are labelled"}],
            "categories": cats}


def main() -> None:
    from features import load_places
    cfg = build_config(load_places())
    (OUTPUT / "category_filters.json").write_text(json.dumps(cfg, indent=2) + "\n")
    tot = sum(c["places"] for c in cfg["categories"].values())
    exc = sum(c["excluded_noise"] for c in cfg["categories"].values())
    print(f"recommendable places: {tot:,}   excluded as noise: {exc:,}\n")
    for cat, c in cfg["categories"].items():
        print(f"{cat:24s} {c['places']:6,d} kept  {c['excluded_noise']:4d} noise   groups: "
              + ", ".join(f"{g} {n}" for g, n in c["type_groups"].items()))
    print("\nwrote output/category_filters.json")


if __name__ == "__main__":
    main()
