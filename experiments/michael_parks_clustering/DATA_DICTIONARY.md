# Data dictionary

Source: `data/nyc_parks/latest/events.json`. Counts below are for that file. Measured values were present in the file. Encoding choices are applied by `prepare_activities.py` and are not new observations.

## Field inspection

| Field | Completeness | Format |
| --- | --- | --- |
| `title` | 882/882 non-empty; 385 distinct; 46 contain a non-ASCII character | String |
| `categories` | 875/882 non-empty; 67 distinct labels; 1 to 10 labels on a session | JSON array of strings, split from `categories_raw` on `\|` |
| `location` | 882/882 non-empty; 312 distinct | Free text, often `room (in Park Name)` |
| `coordinates` | 882/882 strings; 876 are one `latitude, longitude` pair; 6 are two pairs separated by `;` | Decimal degrees in the string. Parsed `latitude` and `longitude` are null on those 6 |
| `starttime` | 865/882 | `YYYY-MM-DDTHH:MM:SS-04:00` |
| `endtime` | 882/882 | Same timestamp form. No session crosses midnight |
| `timezone` | 882/882 | The string `America/New_York` |

The calendar date used in the mapping is the first ten characters of `starttime`. For the 17 sessions with no `starttime`, it is taken from `endtime` and `session_date_basis` is `endtime`.

## Model inputs

These are the only fields intended for the first K-means vector.

| Prepared field | Measured source | Role |
| --- | --- | --- |
| `category:<label>` | `categories` on the combined sessions | Multi-hot. Present label = 1, otherwise 0. Not an ordinal id |
| `easting_km`, `northing_km` | One parsed latitude and longitude | Equirectangular kilometers from the median of model-ready points |
| `easting_km_weighted`, `northing_km_weighted` | The two kilometer columns | Same coordinates after the variance weight in `model_specification.json` |

The model vocabulary has 65 labels. Two source labels, `Community Input Meetings` and `Virtual/Online Events`, occur only on activities excluded below, so they have no column.

An activity enters `feature_matrix.csv` only when it has at least one category, exactly one measured point, and a location string that does not contain the words `virtual` or `online`. The excluded activities remain in `activities.csv` with `model_ready` false:

| Reason | Activities | Sessions |
| --- | ---: | ---: |
| `location_text_is_virtual_or_online` | 9 | 12 |
| `no_single_measured_point` | 3 | 6 |
| `no_category_labels` | 2 | 7 |

The virtual rows do have coordinates. Those coordinates are not used, because the location text says the session is virtual or online and the same point is repeated for that location string. Treating the point as a meeting place would be an assumption. The two-point coordinates are also left unused rather than averaged.

## Metadata

Kept on the activity or in `session_mapping.csv`, and not placed in the numeric vector.

| Field | What it is |
| --- | --- |
| `title`, `normalized_title` | Display text and the grouping key. Not a numeric feature |
| `activity_id` | Stable hash of the grouping key. Not a numeric feature |
| `guid`, `source_id` | Original session id and the dataset id `w3wp-dpdi` |
| `description` | Representative source description |
| `starttime`, `endtime`, `session_date` | Session schedule. Time is not a feature in this first experiment |
| `location`, `park_names`, `park_ids` | Source place text. Park id is missing on 214 source sessions |
| `coordinates`, `latitude`, `longitude` | Original position, including values withheld from the model vector |

## Unavailable

| Information | What the file contains |
| --- | --- |
| Confirmed price | No price field. The word "free" inside a description is prose, not a recorded price |
| User preferences | No user, preference, vote, or rating records |

## Encoding assumptions

These are choices, not measurements:

- Nested category lists describe one activity. Forest Fitness is the only case: five sessions list `Fitness`, `Outdoor Fitness`, and `Exercise Classes`; two list only the first two. The activity uses the union.
- Incomparable category lists at the same title and location would stay separate. None occurred.
- Category columns are not standardized. Standardizing each column would give a rare label a larger step than a common one.
- Location uses spherical Earth radius 6371 km, a fixed median origin, and no elevation.
- One weight multiplies both location columns so their combined population variance equals the combined population variance of the category columns. On this file the weight is about 0.1294. A difference in one category column then has the same squared Euclidean length as about 7.73 km along one projected axis.
