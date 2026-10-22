"""Create the SideQuest tables and load the collected CSVs into Postgres."""

import csv
import html
import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TABLES = (
    "users",
    "activities",
    "categories",
    "activity_categories",
    "rooms",
    "room_members",
    "preferences",
)
PLACEHOLDER_USERS = (
    ("Alex", 21),
    ("Jordan", 22),
    ("Sam", 20),
)


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


def split_values(cell):
    """Split a pipe-joined cell into stripped, non-empty values."""
    return [part.strip() for part in (cell or "").split("|") if part.strip()]


def blank_to_none(value):
    value = (value or "").strip()
    return value or None


def parse_number(value):
    return blank_to_none(value)


def add_categories(cur, activity_id, names):
    for name in names:
        cur.execute(
            """
            INSERT INTO categories (name)
            VALUES (%s)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING category_id
            """,
            (name,),
        )
        category_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO activity_categories (activity_id, category_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (activity_id, category_id),
        )


def insert_activity(cur, **fields):
    cur.execute(
        """
        INSERT INTO activities (
            source, source_item_id, title, description, location,
            latitude, longitude, starttime, endtime, timezone,
            price_currency, price_min, price_max, url, status, collected_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING activity_id
        """,
        (
            fields["source"],
            fields["source_item_id"],
            fields["title"],
            fields.get("description"),
            fields.get("location"),
            fields.get("latitude"),
            fields.get("longitude"),
            fields.get("starttime"),
            fields.get("endtime"),
            fields.get("timezone"),
            fields.get("price_currency"),
            fields.get("price_min"),
            fields.get("price_max"),
            fields.get("url"),
            fields.get("status"),
            fields.get("collected_at"),
        ),
    )
    return cur.fetchone()[0]


def load_parks(cur):
    path = DATA / "nyc_parks" / "latest" / "events.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            park_name = blank_to_none(html.unescape(row.get("park_names") or ""))
            location = blank_to_none(row.get("location")) or park_name
            activity_id = insert_activity(
                cur,
                source="nyc_parks",
                source_item_id=row["guid"],
                title=row["title"],
                description=blank_to_none(row.get("description")),
                location=location,
                latitude=parse_number(row.get("latitude")),
                longitude=parse_number(row.get("longitude")),
                starttime=blank_to_none(row.get("starttime")),
                endtime=blank_to_none(row.get("endtime")),
                timezone=blank_to_none(row.get("timezone")),
                url=blank_to_none(row.get("link")),
                collected_at=blank_to_none(row.get("collected_at")),
            )
            add_categories(cur, activity_id, split_values(row.get("categories")))
    return path


def load_ticketmaster(cur):
    path = DATA / "ticketmaster" / "latest" / "events.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            venue = blank_to_none(row.get("venue_name"))
            address = blank_to_none(row.get("address"))
            city = blank_to_none(row.get("venue_city"))
            location = ", ".join(part for part in (venue, address, city) if part)
            activity_id = insert_activity(
                cur,
                source="ticketmaster",
                source_item_id=row["event_id"],
                title=row["title"],
                location=location or None,
                latitude=parse_number(row.get("latitude")),
                longitude=parse_number(row.get("longitude")),
                starttime=blank_to_none(row.get("starttime")),
                timezone=blank_to_none(row.get("timezone")),
                price_currency=blank_to_none(row.get("price_currency")),
                price_min=parse_number(row.get("price_min")),
                price_max=parse_number(row.get("price_max")),
                url=blank_to_none(row.get("ticket_url")),
                status=blank_to_none(row.get("event_status")),
                collected_at=blank_to_none(row.get("collected_at")),
            )
            add_categories(
                cur,
                activity_id,
                [name for name in (blank_to_none(row.get("segment")), blank_to_none(row.get("genre"))) if name],
            )
    return path


def load_places(cur):
    path = DATA / "google_places" / "latest" / "places.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            activity_id = insert_activity(
                cur,
                source="google_places",
                source_item_id=row["place_id"],
                title=row["name"],
                location=blank_to_none(row.get("formatted_address")),
                latitude=parse_number(row.get("latitude")),
                longitude=parse_number(row.get("longitude")),
                price_currency=blank_to_none(row.get("price_currency")),
                price_min=parse_number(row.get("price_min")),
                price_max=parse_number(row.get("price_max")),
                url=blank_to_none(row.get("google_maps_uri")),
                status=blank_to_none(row.get("business_status")),
                collected_at=blank_to_none(row.get("collected_at")),
            )
            add_categories(
                cur,
                activity_id,
                split_values(row.get("types")) + split_values(row.get("search_areas")),
            )
    return path


def seed_example_room(cur):
    """One placeholder room so the new tables are visible. Not a product flow."""
    cur.execute("SELECT user_id, name FROM users ORDER BY user_id")
    members = cur.fetchall()
    organizer_id = members[0][0]
    cur.execute(
        """
        INSERT INTO rooms (
            name, code, status, organizer_user_id, timezone,
            planning_start, planning_end
        )
        VALUES (
            'Friday hangout', 'FRI-01', 'open', %s,
            'America/New_York',
            '2026-10-23 18:00:00-04', '2026-10-23 23:00:00-04'
        )
        RETURNING room_id
        """,
        (organizer_id,),
    )
    room_id = cur.fetchone()[0]
    for user_id, name in members:
        role = "organizer" if user_id == organizer_id else "member"
        cur.execute(
            """
            INSERT INTO room_members (
                room_id, user_id, role, budget_hard, budget_ideal,
                budget_currency, travel_limit_minutes, travel_mode, starting_area,
                free_start, free_end
            )
            VALUES (
                %s, %s, %s, 40, 25, 'USD', 45, 'transit', 'Brooklyn',
                '2026-10-23 18:00:00-04', '2026-10-23 22:00:00-04'
            )
            """,
            (room_id, user_id, role),
        )
    # Alex will not do a BBQ. Jordan will do horror if the group wants it.
    # A blank user_id is the group's own preference.
    alex_id = members[0][0]
    jordan_id = members[1][0]
    cur.execute(
        """
        INSERT INTO preferences (room_id, user_id, label, polarity, strength)
        VALUES
            (%s, %s, 'bbq', 'exclude', 'hard'),
            (%s, %s, 'horror', 'avoid', 'flexible'),
            (%s, NULL, 'outdoors', 'prefer', 'flexible')
        """,
        (room_id, alex_id, room_id, jordan_id, room_id),
    )


def main():
    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set")
    if "railway.internal" in database_url:
        raise SystemExit(
            "DATABASE_URL is the private Railway host. From your laptop, "
            "replace it with DATABASE_PUBLIC_URL (host ends in rlwy.net)."
        )

    schema_sql = (ROOT / "schema.sql").read_text()

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DROP TABLE IF EXISTS
                    matched_plans,
                    votes,
                    deck_options,
                    custom_suggestions,
                    deck_rounds,
                    activity_hours,
                    availability_windows,
                    preferences,
                    user_preferences,
                    room_preferences,
                    room_members,
                    rooms,
                    activity_categories,
                    park_event_categories,
                    place_place_types,
                    place_search_areas,
                    park_events,
                    ticketmaster_events,
                    places,
                    parks,
                    venues,
                    place_types,
                    search_areas,
                    activities,
                    categories,
                    users
                """
            )
            cur.execute(schema_sql)

            for name, age in PLACEHOLDER_USERS:
                cur.execute("INSERT INTO users (name, age) VALUES (%s, %s)", (name, age))
            seed_example_room(cur)

            parks_path = load_parks(cur)
            tm_path = load_ticketmaster(cur)
            places_path = load_places(cur)

            print(f"Loaded {parks_path}")
            print(f"Loaded {tm_path}")
            print(f"Loaded {places_path}")
            for table in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"{table}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
