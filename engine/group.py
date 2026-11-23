#!/usr/bin/env python3
"""Room decision logic: the organizer's room settings + each member's private preferences -> one shared deck,
then the group's swipes -> the winner.

App flow
  1. Organizer creates a Room: borough(s), group size, when (date + time).
  2. Each Member privately sets: categories, max price, optional toggles (kids / outdoors / nightlife),
     optional type groups and cuisines, and whether they need wheelchair access.
  3. recommend_room(room, members)  -> one shared 10-card deck
  4. everyone swipes; pick_winner(deck, votes) -> the most-liked place (or "no match" + a fresh deck)

Hard limits (never broken)
  - borough is one of the room's boroughs
  - price <= the LOWEST member limit (nobody is priced out; limits stay private)
  - open at `when` for at least OPEN_MINUTES (places known to be closed are excluded; unknown hours are
    allowed, labelled "Hours not listed" and ranked lower)
  - wheelchair-accessible entrance confirmed, if any member needs it
  - the place's type is a real, recommendable type for its category (category_config.TYPE_GROUPS)
  - not clearly bad: rated below RATING_FLOOR with at least RATING_FLOOR_MIN_COUNT ratings
Soft, per member (ranking + "who is this card for"): categories, types, cuisines, toggles.

The fitted model (output/model_v1.json) is used to pick the clusters that fit the whole group best: mean member
distance + the worst-off member's distance. Ranking uses the same group score minus a rating bonus, then a fair
fill gives each slot to the member with the fewest suitable cards so far.

    python group.py        # runs the example rooms in EXAMPLES -> output/group_demo.md / .json
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from category_config import CARD_FIELDS, TYPE_GROUPS, annotate
from features import BOROUGHS, CATEGORIES, OUTPUT, query_vector, raw_vibes
from recommend import (DECK_SIZE, MAX_PER_SUBCATEGORY, MODEL_PATH, PRICE_LABEL, QUALITY_WEIGHT, VIBE_TOGGLES,
                       Recommender, expressed_mask, place_type)

OPEN_MINUTES = 90                  # a place must be open this long from the room's start time
UNKNOWN_HOURS_PENALTY = 0.15       # ranking penalty for places whose hours Google doesn't list
MIN_CANDIDATES_PER_MEMBER = 5
WORST_OFF_WEIGHT = 1.0
MATCH_MIN_LIKES = 2                # a winner needs at least this many likes
RATING_FLOOR = 3.5                 # never recommend a place rated below this ...
RATING_FLOOR_MIN_COUNT = 10        # ... once it has at least this many ratings (clearly bad, not just new)
WEEK = 7 * 24 * 60
TAG_FLAGS = [("outdoor_seating", "Outdoor seating"), ("live_music", "Live music"), ("good_for_children", "Kid-friendly"),
             ("allows_dogs", "Dog-friendly"), ("reservable", "Takes reservations"), ("serves_cocktails", "Cocktails"),
             ("good_for_watching_sports", "Sports on TV"), ("serves_vegetarian", "Vegetarian options"),
             ("serves_brunch", "Brunch")]


@dataclass
class Room:
    boroughs: list[str]
    group_size: int
    when: datetime


@dataclass
class Member:
    name: str
    max_price: int
    categories: list[str]
    toggles: list[str] = field(default_factory=list)          # kids / outdoors / nightlife (+ dogs, groups, live_music)
    types: dict[str, list[str]] = field(default_factory=dict)  # optional: category -> type groups they want
    cuisines: list[str] = field(default_factory=list)          # optional, restaurants only
    needs_wheelchair: bool = False


def minute_of_week(t: datetime) -> int:
    """Google's week starts Sunday 00:00."""
    return ((t.weekday() + 1) % 7) * 1440 + t.hour * 60 + t.minute


def fmt_minute(m: int) -> str:
    m %= WEEK
    h, mi = divmod(m % 1440, 60)
    return datetime(2000, 1, 1, h, mi).strftime("%-I:%M %p").replace(":00 ", " ")


class GroupRecommender:
    def __init__(self, rec: Recommender):
        self.rec = rec
        self.P = annotate(rec.places)
        self.vib = raw_vibes(self.P)
        self.cat = self.P["activity_category"].to_numpy()
        self.price = self.P["price_final"].to_numpy()
        self.borough = self.P["borough"].to_numpy()
        self.type_group = self.P["type_group"].to_numpy()
        self.cuisine_group = self.P["cuisine_group"].to_numpy()
        clearly_bad = ((self.P["rating"] < RATING_FLOOR) & (self.P["rating_count"] >= RATING_FLOOR_MIN_COUNT)).fillna(False)
        self.recommendable = (self.P["type_group"].notna() & ~clearly_bad).to_numpy(dtype=bool)
        # opening hours -> flat interval arrays for fast "open at t" checks
        rows, starts, ends = [], [], []
        for i, s in enumerate(self.P["open_intervals"]):
            if isinstance(s, str):
                for a, b in json.loads(s):
                    rows.append(i); starts.append(a); ends.append(b)
        self.iv_row, self.iv_start, self.iv_end = np.array(rows), np.array(starts), np.array(ends)
        self.has_hours = self.P["open_intervals"].notna().to_numpy()

    # -- opening hours ---------------------------------------------------------------------------
    def _covers(self, a: int, b: int) -> np.ndarray:
        """Places with one interval covering [a, b) within the week."""
        ok = np.zeros(len(self.P), dtype=bool)
        hit = (self.iv_start <= a) & (self.iv_end >= b)
        ok[self.iv_row[hit]] = True
        return ok

    def open_at(self, when: datetime, minutes: int = OPEN_MINUTES) -> np.ndarray:
        """True = open for `minutes` from `when`; False = known closed or closing too soon; unknown -> True."""
        t = minute_of_week(when)
        end = t + minutes
        if end <= WEEK:
            known_open = self._covers(t, end)
        else:                                            # spans Saturday -> Sunday midnight
            known_open = self._covers(t, WEEK) & self._covers(0, end - WEEK)
        return known_open | ~self.has_hours

    def open_until(self, i: int, when: datetime) -> str:
        if not self.has_hours[i]:
            return "Hours not listed"
        t = minute_of_week(when)
        m = (self.iv_row == i) & (self.iv_start <= t) & (self.iv_end > t)
        if not m.any():
            return "Closed then"
        start, end = int(self.iv_start[m].min()), int(self.iv_end[m].max())
        if start == 0 and end == WEEK:
            return "Open 24 hours"
        if end == WEEK:                                  # continues past Saturday midnight: add the wrap piece
            nxt = (self.iv_row == i) & (self.iv_start == 0)
            end = WEEK + (int(self.iv_end[nxt].max()) if nxt.any() else 0)
        return f"Open until {fmt_minute(end)}"

    # -- members -----------------------------------------------------------------------------------
    def _queries(self, m: Member):
        vibes = {}
        for t in m.toggles:
            vibes.update(VIBE_TOGGLES.get(t, {}))
        mask = expressed_mask(vibes)
        return [query_vector([c], m.max_price, self.rec.spec, self.rec.w_cat, vibes) for c in m.categories], mask, vibes

    @staticmethod
    def _dist(Y, queries, mask):
        return np.min([np.sqrt(((Y[:, mask] - q[mask]) ** 2).sum(axis=1)) for q in queries], axis=0)

    def suits(self, m: Member, idx: np.ndarray, vibes: dict) -> np.ndarray:
        """Would this member want the card? Their category, budget, chosen types/cuisines, and no toggle the place
        is KNOWN to fail (unknown flags get the benefit of the doubt)."""
        ok = np.isin(self.cat[idx], m.categories) & (self.price[idx] <= m.max_price)
        for cat, groups in m.types.items():
            if groups:
                ok &= (self.cat[idx] != cat) | np.isin(self.type_group[idx], groups)
        if m.cuisines:
            ok &= (self.cat[idx] != "Restaurants") | np.isin(self.cuisine_group[idx], m.cuisines)
        for f in vibes:
            ok &= ~(self.vib[f].to_numpy()[idx] == 0)
        return ok

    # -- cards ---------------------------------------------------------------------------------------
    def card(self, i: int, when: datetime) -> dict:
        p = self.P.loc[i]
        cat = p["activity_category"]
        rating = None if pd.isna(p["rating"]) else f"{p['rating']:.1f}★ ({int(p['rating_count']):,})"
        est = p["price_final_source"] == "category_estimate"
        if pd.notna(p["price_min_usd"]):
            price = (f"${int(p['price_min_usd'])}–{int(p['price_max_usd'])} per person" if pd.notna(p["price_max_usd"])
                     else f"${int(p['price_min_usd'])}+ per person")
        else:
            price = "Free" if p["price_final"] == 0 else PRICE_LABEL[int(p["price_final"])] + (" (estimated)" if est else "")
        values = {
            "cuisine": p["cuisine_group"] if isinstance(p["cuisine_group"], str) else place_type(p),
            "type": place_type(p),
            "price_range": price,
            "price_note": ("Free" if p["price_final"] == 0
                           else f"{PRICE_LABEL[int(p['price_final'])]} · price estimated" if est else price),
            "rating": rating,
            "neighborhood": f"{p['neighborhood']}, {p['borough']}",
            "open_until": self.open_until(i, when),
            "inspection_grade": f"Health grade {p['inspection_grade']}" if pd.notna(p["inspection_grade"]) else None,
            "summary": p["generative_summary"] if pd.notna(p["generative_summary"]) else None,
            "tags": [label for col, label in TAG_FLAGS if p[col] is True],
            "free": "Free",
            "free_if_library": "Free" if p["type_group"] == "Libraries" else None,
            "size": f"{p['acres']:.0f} acres" if pd.notna(p["acres"]) and p["acres"] >= 1 else None,
            "nearest_subway": (f"{p['nearest_subway']} · {int(round(p['nearest_subway_m'] / 80))} min walk"
                               if pd.notna(p["nearest_subway_m"]) else None),
            "official_label": {"nyc_parks": "Official NYC park",
                               "greenthumb": "GreenThumb community garden"}.get(p["verified_by"]),
            "famous": "Famous landmark" if pd.notna(p["wikidata_sitelinks"]) and p["wikidata_sitelinks"] >= 10 else None,
            "venue_note": "Venue: check what's on",
        }
        return {"id": p["master_id"], "name": p["name"], "category": cat, "type_group": p["type_group"],
                "fields": {k: values[k] for k in CARD_FIELDS[cat] if values.get(k) not in (None, [], "")},
                "cluster": int(self.rec.labels[i]), "cluster_name": self.rec.names[int(self.rec.labels[i])],
                "lat": float(p["lat"]), "lng": float(p["lng"]),
                "maps_uri": p["maps_uri"] if pd.notna(p["maps_uri"]) else None}

    # -- main ---------------------------------------------------------------------------------------
    def recommend_room(self, room: Room, members: list[Member], n: int = DECK_SIZE,
                       exclude: set[str] | None = None) -> dict:
        if not members:
            raise ValueError("no members yet")
        if len(members) > room.group_size:
            raise ValueError(f"room is for {room.group_size} people, got {len(members)}")
        bad_b = [b for b in room.boroughs if b not in BOROUGHS]
        if not room.boroughs or bad_b:
            raise ValueError(f"pick 1+ boroughs from {BOROUGHS}")
        for m in members:
            bad = [c for c in m.categories if c not in CATEGORIES] + [t for t in m.toggles if t not in VIBE_TOGGLES]
            bad += [g for c, gs in m.types.items() for g in gs if g not in TYPE_GROUPS.get(c, {})]
            if bad or not m.categories:
                raise ValueError(f"{m.name}: bad or missing settings {bad}")

        P = self.P
        price_cap = min(m.max_price for m in members)
        wanted = sorted({c for m in members for c in m.categories})
        ok = (np.isin(self.cat, wanted) & self.recommendable & (self.price <= price_cap)
              & np.isin(self.borough, room.boroughs) & self.open_at(room.when))
        wheelchair = any(m.needs_wheelchair for m in members)
        if wheelchair:
            ok &= P["wheelchair_entrance"].eq(True).fillna(False).to_numpy(dtype=bool)
        if exclude:
            ok &= ~P["master_id"].isin(exclude).to_numpy()
        limits = {"boroughs": room.boroughs, "when": room.when.strftime("%a %b %-d, %-I:%M %p"),
                  "max_price": PRICE_LABEL[price_cap], "categories": wanted, "wheelchair_access": wheelchair}
        base = {"room_limits": limits, "members_joined": f"{len(members)} of {room.group_size}"}
        if not ok.any():
            return {**base, "deck": [], "message": "Nothing fits everyone's limits at that time. "
                                                   "Try another time, more boroughs or a higher budget."}

        mq = [self._queries(m) for m in members]
        cd = np.array([self._dist(self.rec.centers, qs, mask) for qs, mask, _ in mq])
        order = np.argsort(cd.mean(axis=0) + WORST_OFF_WEIGHT * cd.max(axis=0), kind="stable")
        pool, used = np.zeros(len(P), dtype=bool), []
        for c in order:
            used.append(int(c))
            pool |= ok & (self.rec.labels == c)
            idx = np.flatnonzero(pool)
            if len(idx) >= 3 * n and all(self.suits(m, idx, v).sum() >= MIN_CANDIDATES_PER_MEMBER
                                         for m, (_, _, v) in zip(members, mq)):
                break
        idx = np.flatnonzero(pool)

        pd_ = np.array([self._dist(self.rec.X[idx], qs, mask) for qs, mask, _ in mq])
        score = (pd_.mean(axis=0) + WORST_OFF_WEIGHT * pd_.max(axis=0) - QUALITY_WEIGHT * self.rec.qual[idx]
                 + UNKNOWN_HOURS_PENALTY * ~self.has_hours[idx])
        ranked = idx[np.lexsort((P["master_id"].to_numpy()[idx], score))]
        suits = {m.name: dict(zip(ranked, self.suits(m, ranked, v))) for m, (_, _, v) in zip(members, mq)}

        deck, names, per_sub = [], set(), {}
        served = {m.name: 0 for m in members}

        def allowed(i):
            return (P.at[i, "name"].strip().lower() not in names
                    and per_sub.get(P.at[i, "subcategory"], 0) < MAX_PER_SUBCATEGORY)

        while len(deck) < n:
            pick = None
            for who in sorted(served, key=lambda k: served[k]):              # least-served member first
                pick = next((i for i in ranked if i not in deck and allowed(i) and suits[who][i]), None)
                if pick is not None:
                    break
            if pick is None:
                pick = next((i for i in ranked if i not in deck and allowed(i)), None)
            if pick is None:
                break
            deck.append(pick)
            names.add(P.at[pick, "name"].strip().lower())
            per_sub[P.at[pick, "subcategory"]] = per_sub.get(P.at[pick, "subcategory"], 0) + 1
            for who in served:
                served[who] += int(suits[who][pick])

        cards = []
        for i in deck:
            c = self.card(i, room.when)
            c["for"] = [m.name for m in members if suits[m.name][i]]
            cards.append(c)
        unserved = {}
        for m, (_, _, v) in zip(members, mq):
            if served[m.name] == 0:
                any_fit = self.suits(m, np.flatnonzero(ok), v).sum()
                unserved[m.name] = ("nothing in their picks fits the room's limits (budget, borough, time)"
                                    if any_fit == 0 else "their picks rank below what the rest of the group shares")
        return {**base, "clusters_used": [{"id": c, "name": self.rec.names[c]} for c in used],
                "cards_per_member": served, "unserved_members": unserved, "deck": cards}


def pick_winner(deck: list[dict], votes: dict[str, dict[str, bool]], min_likes: int = MATCH_MIN_LIKES) -> dict:
    """Most-liked card wins. Ties -> the card that suits more members -> earlier in the deck (higher group rank).

    votes: {member_name: {card_id: True (like) / False (skip)}}; missing votes are not likes.
    Returns {"match": card, "likes_for_match": n, "liked_by": [...]} or {"match": None, ...} when the best card has
    fewer than `min_likes` likes; then call recommend_room(..., exclude=<shown ids>) for a fresh deck.
    """
    if not deck:
        return {"match": None, "reason": "empty deck"}
    tally = []
    for pos, c in enumerate(deck):
        liked_by = [who for who, v in votes.items() if v.get(c["id"]) is True]
        tally.append((len(liked_by), len(c.get("for", [])), -pos, c, liked_by))
    likes, _, _, card, liked_by = max(tally, key=lambda t: t[:3])
    summary = {t[3]["id"]: t[0] for t in tally}
    if likes < min(min_likes, len(votes)):
        return {"match": None, "reason": f"best card has {likes} like(s); deal a new deck", "likes": summary}
    return {"match": card, "likes_for_match": likes, "liked_by": liked_by, "likes": summary}


EXAMPLES = {
    "Friday night in Manhattan, mixed budgets": (
        Room(["Manhattan"], 5, datetime(2026, 12, 4, 20, 0)),
        [Member("Ana", 3, ["Bars & Nightlife"], ["nightlife"], types={"Bars & Nightlife": ["Cocktail & wine bars"]}),
         Member("Ben", 2, ["Restaurants"], cuisines=["Southeast Asian", "Japanese & sushi"]),
         Member("Chi", 2, ["Bars & Nightlife", "Restaurants"]),
         Member("Dev", 4, ["Shows & Live Events"], types={"Shows & Live Events": ["Comedy"]}),
         Member("Eli", 2, ["Restaurants"], ["outdoors"])]),
    "Sunday morning with kids in Queens/Brooklyn": (
        Room(["Queens", "Brooklyn"], 4, datetime(2026, 12, 6, 10, 30)),
        [Member("Fay", 1, ["Parks & Outdoors"], ["kids"], types={"Parks & Outdoors": ["Playgrounds", "Parks"]}),
         Member("Gus", 2, ["Museums & Galleries", "Parks & Outdoors"]),
         Member("Hal", 1, ["Cafes & Desserts"], ["kids"]),
         Member("Ivy", 1, ["Parks & Outdoors", "Games & Indoor Fun"], needs_wheelchair=True)]),
    "Late Saturday in Brooklyn": (
        Room(["Brooklyn"], 3, datetime(2026, 12, 5, 23, 30)),
        [Member("Jo", 2, ["Bars & Nightlife"]), Member("Kai", 1, ["Restaurants", "Cafes & Desserts"]),
         Member("Lu", 2, ["Bars & Nightlife", "Restaurants"], ["live_music"])]),
}


def main() -> None:
    g = GroupRecommender(Recommender.load(MODEL_PATH))
    lines = ["# Room decks (example rooms)\n",
             "Made-up rooms for testing. Each card lists who it's for; fields depend on the category.\n"]
    out_json = {}
    for title, (room, members) in EXAMPLES.items():
        out = g.recommend_room(room, members)
        # example vote: everyone likes the cards that are "for" them
        votes = {m.name: {c["id"]: (m.name in c["for"]) for c in out["deck"]} for m in members}
        win = pick_winner(out["deck"], votes)
        out_json[title] = {"room": {**asdict(room), "when": room.when.isoformat()},
                           "members": [asdict(m) for m in members], **out, "example_winner": win}
        print(f"\n== {title}\n   limits: {out['room_limits']}\n   cards per member: {out.get('cards_per_member')}")
        lines += [f"## {title}\n",
                  f"Room: {', '.join(room.boroughs)} · {room.group_size} people · {out['room_limits']['when']}  ",
                  f"Group limits: max price {out['room_limits']['max_price']}"
                  f"{', wheelchair access' if out['room_limits']['wheelchair_access'] else ''}\n",
                  "| member | max price | categories | toggles | types / cuisines |", "|---|---|---|---|---|"]
        for m in members:
            extra = "; ".join([f"{c}: {', '.join(gs)}" for c, gs in m.types.items()] + m.cuisines
                              + (["needs wheelchair access"] if m.needs_wheelchair else []))
            lines.append(f"| {m.name} | {PRICE_LABEL[m.max_price]} | {', '.join(m.categories)} | "
                         f"{', '.join(m.toggles) or '–'} | {extra or '–'} |")
        lines.append(f"\nCards per member: {out.get('cards_per_member')}  ")
        for who, why in out.get("unserved_members", {}).items():
            lines.append(f"No card for {who}: {why}.  ")
            print(f"   no card for {who}: {why}")
        lines += ["", "| # | place | category | card fields | for |", "|---|---|---|---|---|"]
        for k, c in enumerate(out["deck"], 1):
            f = " · ".join(str(v) if not isinstance(v, list) else ", ".join(v)
                           for key, v in c["fields"].items() if key != "summary")
            lines.append(f"| {k} | {c['name']} | {c['category']} | {f} | {', '.join(c['for']) or '–'} |")
            print(f"   {k:2d}. {c['name']} [{c['category']}] {f[:120]} · for {', '.join(c['for'])}")
        if win["match"]:
            lines.append(f"\nExample vote (everyone likes the cards that suit them): winner **{win['match']['name']}** "
                         f"with {win['likes_for_match']} likes ({', '.join(win['liked_by'])}).\n")
            print(f"   winner: {win['match']['name']} ({win['likes_for_match']} likes)")
    (OUTPUT / "group_demo.md").write_text("\n".join(lines) + "\n")
    (OUTPUT / "group_demo.json").write_text(json.dumps(out_json, indent=2, default=str) + "\n")
    print("\nwrote group_demo.md / .json")


if __name__ == "__main__":
    main()
