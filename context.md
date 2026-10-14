# Side Quest context

Living notes for what is built and what comes next. The product brief remains [README.md](README.md). Do not treat a note here as a built feature.

A request such as outdoor activities in Manhattan or Brooklyn filters collected records by category and place, then ranks what fits. Missing price, time, or borough stays unknown. It is not treated as free or as a match.

## Implemented

### NYC Parks events

`collect_parks_events.py` pulls the public upcoming-14-days feed (`w3wp-dpdi`). No API key.

- Run: `python3 collect_parks_events.py`
- Output: `data/nyc_parks/latest/` and `data/nyc_parks/snapshots/YYYY-MM-DD/`
- First pull on Oct 13, 2026 saved 882 events. A second pull the same night found 0 new `guid`s.
- An event is new only when its `guid` was absent from the previous snapshot. The first run is a baseline.
- Times are America/New_York. The feed has no price field, so nothing is marked free.
- Park ids starting with M or B are a borough signal. 214 events in that pull had no park id, so their borough is unknown.

### Google Places

`collect_google_places.py` calls Places API (New) Text Search. The key lives in `.env` as `GOOGLE_MAPS_API_KEY`. That file is gitignored.

- Run: `python3 collect_google_places.py`
- Output: `data/google_places/latest/` and durable ids in `data/google_places/place_ids.json`
- Oct 13, 2026 sample: 10 outdoor places and 10 restaurants in each of Manhattan and Brooklyn (38 after deduping). 18 of 20 restaurants had a USD `priceRange`. Outdoor places did not.
- `price_min` is inclusive. `price_max` is exclusive. `price_max_unbounded` means Google sent no top. A blank range is unknown, not $0.
- `search_areas` is the query rectangle, not a verified borough.
- Place IDs may be kept. Latitude and longitude in the Oct 13 file must be deleted after Nov 12, 2026. Names, addresses, hours, and prices are a sample, not a permanent Google catalog. Show attribution as Google Maps.

### Ticketmaster events

`collect_ticketmaster_events.py` calls the Discovery API. The consumer key lives in `.env` as `TICKETMASTER_API_KEY`. The consumer secret is not stored.

- Run: `python3 collect_ticketmaster_events.py`
- Output: `data/ticketmaster/latest/` and `data/ticketmaster/snapshots/YYYY-MM-DD/`
- Oct 13, 2026 pull: 159 music, sports, and arts events in New York and Brooklyn over the next 14 days. 21 had a USD price range, mostly music. A missing price is unknown, not free. A 0 to 0 range is stored as missing.
- A supplied price does not mean tickets remain. `onsale` is Ticketmaster's sale status, not group inventory.
- `venue_city` is the venue's city name. "New York" is not recorded as a verified borough.

## Later

Spend the $300 Cloud credit only after the free monthly Maps calls are used up. Do not prefetch all of NYC.

- **Routes API.** Travel time from each person's starting area to a candidate, and a transit fare when Google has one. Use it on the short deck. This is the fairness and total-budget check.
- **Geocoding.** Turn a neighborhood into coordinates. Keep the starting point approximate.
- **Places.** Keep for venues and restaurant ranges. More calls will not add prices to parks or museums.
- **Cloud Run, Cloud SQL, Cloud Scheduler.** Host the room API, store rooms, preferences, and private votes, and run the Parks pull daily.
- **Gemini.** Later, turn a plain-language request into filters, or write "why this fits" from checks that already passed. Grounding with Google Maps can look up places if attribution and place IDs stay attached. It does not replace the hard filter or the private vote.
- **BigQuery.** Later, for match-rate and constraint questions on our own room data and the Parks file. Not a store for Google Places content.
- **Room product.** Create/join, intake, feasible deck, private yes/no, unanimous match, and plan handoff are not built.
