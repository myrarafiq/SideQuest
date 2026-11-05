"""Bare Side Quest skeleton: one HTML page, a few Flask routes, Railway Postgres."""

import os
import secrets
import string
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, render_template, request
from psycopg2 import errors

ROOT = Path(__file__).resolve().parent
CODE_ALPHABET = string.ascii_uppercase + string.digits


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

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-skeleton-only")


def database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Put the Railway public URL in .env.")
    on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
    if "railway.internal" in url and not on_railway:
        raise RuntimeError(
            "DATABASE_URL is the private Railway host. From your laptop, use the "
            "public URL (host ends in rlwy.net)."
        )
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def get_conn():
    return psycopg2.connect(database_url(), cursor_factory=psycopg2.extras.RealDictCursor)


def clean_name(value, label, limit=80):
    name = " ".join((value or "").split())
    if not name:
        raise ValueError(f"{label} is required.")
    if len(name) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")
    return name


def new_room_code(cur):
    for _ in range(8):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        cur.execute("SELECT 1 FROM rooms WHERE code = %s", (code,))
        if cur.fetchone() is None:
            return code
    raise RuntimeError("Could not make a unique room code.")


def parse_user_id(value):
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("Create or join the room again before saving constraints.")
    if user_id < 1:
        raise ValueError("Create or join the room again before saving constraints.")
    return user_id


def parse_money(value, label, required):
    text = "" if value is None else str(value).strip()
    if not text:
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} must be a number.")
    if amount < 0:
        raise ValueError(f"{label} cannot be negative.")
    if amount > Decimal("100000"):
        raise ValueError(f"{label} is too large.")
    return amount


def parse_minutes(value):
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("Travel limit is required.")
    try:
        minutes = int(text)
    except ValueError:
        raise ValueError("Travel limit must be a whole number of minutes.")
    if minutes < 1 or minutes > 1440:
        raise ValueError("Travel limit must be between 1 and 1440 minutes.")
    return minutes


def parse_local_time(value, label, timezone_name):
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{label} is required.")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{label} must be a valid date and time.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def local_input_value(moment, timezone_name):
    if moment is None:
        return None
    return moment.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%dT%H:%M")


def money_text(amount):
    if amount is None:
        return None
    return format(amount, "f")


def room_payload(cur, code, you_user_id=None):
    cur.execute(
        """
        SELECT room_id, name, code, status, timezone
        FROM rooms
        WHERE code = %s
        """,
        (code,),
    )
    room = cur.fetchone()
    if room is None:
        return None
    cur.execute(
        """
        SELECT u.user_id, u.name, m.role, m.ready,
               m.budget_hard, m.budget_ideal, m.budget_currency,
               m.travel_limit_minutes, m.starting_area, m.free_start, m.free_end
        FROM room_members m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.room_id = %s
        ORDER BY m.role DESC, u.name
        """,
        (room["room_id"],),
    )
    rows = cur.fetchall()
    timezone_name = room["timezone"] or "America/New_York"
    members = [
        {"name": row["name"], "role": row["role"], "ready": row["ready"]}
        for row in rows
    ]
    payload = {
        "name": room["name"],
        "code": room["code"],
        "status": room["status"],
        "members": members,
    }
    if you_user_id is None:
        return payload
    you = next((row for row in rows if row["user_id"] == you_user_id), None)
    if you is None:
        return payload
    payload["you"] = {
        "user_id": you["user_id"],
        "name": you["name"],
        "role": you["role"],
        "ready": you["ready"],
        "budget_hard": money_text(you["budget_hard"]),
        "budget_ideal": money_text(you["budget_ideal"]),
        "budget_currency": you["budget_currency"],
        "travel_limit_minutes": you["travel_limit_minutes"],
        "starting_area": you["starting_area"],
        "free_start_local": local_input_value(you["free_start"], timezone_name),
        "free_end_local": local_input_value(you["free_end"], timezone_name),
    }
    return payload


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'rooms'
                    ) AS ready
                    """
                )
                ready = cur.fetchone()["ready"]
        return jsonify({"ok": True, "tables_ready": ready})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.get("/api/activities")
def activities():
    """A short slice of collected listings so the page can show the database is live."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, location, source, starttime, url
                    FROM activities
                    ORDER BY starttime NULLS LAST, activity_id
                    LIMIT 12
                    """
                )
                rows = cur.fetchall()
    except errors.UndefinedTable:
        return jsonify(
            {
                "activities": [],
                "error": "The activities table is not there yet. Run python load_data.py once.",
            }
        )
    except Exception as exc:
        return jsonify({"activities": [], "error": str(exc)}), 503

    items = []
    for row in rows:
        start = row["starttime"]
        items.append(
            {
                "title": row["title"],
                "location": row["location"],
                "source": row["source"],
                "starttime": start.isoformat() if start else None,
                "url": row["url"],
            }
        )
    return jsonify({"activities": items})


@app.post("/api/rooms")
def create_room():
    body = request.get_json(silent=True) or {}
    try:
        person = clean_name(body.get("name"), "Your name")
        room_name = clean_name(body.get("room_name"), "Room name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name) VALUES (%s) RETURNING user_id",
                    (person,),
                )
                user_id = cur.fetchone()["user_id"]
                code = new_room_code(cur)
                cur.execute(
                    """
                    INSERT INTO rooms (name, code, organizer_user_id)
                    VALUES (%s, %s, %s)
                    RETURNING room_id
                    """,
                    (room_name, code, user_id),
                )
                room_id = cur.fetchone()["room_id"]
                cur.execute(
                    """
                    INSERT INTO room_members (room_id, user_id, role, ready)
                    VALUES (%s, %s, 'organizer', FALSE)
                    """,
                    (room_id, user_id),
                )
                payload = room_payload(cur, code, user_id)
    except errors.UndefinedTable:
        return jsonify({"error": "Tables are missing. Run python load_data.py once."}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(payload), 201


@app.post("/api/rooms/join")
def join_room():
    body = request.get_json(silent=True) or {}
    try:
        person = clean_name(body.get("name"), "Your name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    code = (body.get("code") or "").strip().upper()
    if not code:
        return jsonify({"error": "Room code is required."}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT room_id, status FROM rooms WHERE code = %s", (code,))
                room = cur.fetchone()
                if room is None:
                    return jsonify({"error": "No room with that code."}), 404
                if room["status"] not in ("open", "voting"):
                    return jsonify({"error": "That room is closed."}), 409
                cur.execute(
                    "INSERT INTO users (name) VALUES (%s) RETURNING user_id",
                    (person,),
                )
                user_id = cur.fetchone()["user_id"]
                cur.execute(
                    """
                    INSERT INTO room_members (room_id, user_id, role)
                    VALUES (%s, %s, 'guest')
                    """,
                    (room["room_id"], user_id),
                )
                payload = room_payload(cur, code, user_id)
    except errors.UndefinedTable:
        return jsonify({"error": "Tables are missing. Run python load_data.py once."}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(payload)


@app.post("/api/rooms/<code>/intake")
def save_intake(code):
    """Save one person's constraints. The shared room view only learns that they are ready."""
    body = request.get_json(silent=True) or {}
    code = code.strip().upper()
    try:
        user_id = parse_user_id(body.get("user_id"))
        budget_hard = parse_money(body.get("budget_hard"), "Hard budget", required=True)
        budget_ideal = parse_money(body.get("budget_ideal"), "Ideal budget", required=False)
        if budget_ideal is not None and budget_ideal > budget_hard:
            raise ValueError("Ideal budget cannot be higher than the hard budget.")
        starting_area = clean_name(body.get("starting_area"), "Starting area")
        travel_limit = parse_minutes(body.get("travel_limit_minutes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT room_id, status, timezone
                    FROM rooms
                    WHERE code = %s
                    """,
                    (code,),
                )
                room = cur.fetchone()
                if room is None:
                    return jsonify({"error": "No room with that code."}), 404
                if room["status"] not in ("open", "voting"):
                    return jsonify({"error": "That room is closed."}), 409
                timezone_name = room["timezone"] or "America/New_York"
                try:
                    free_start = parse_local_time(body.get("free_start"), "Free from", timezone_name)
                    free_end = parse_local_time(body.get("free_end"), "Free until", timezone_name)
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
                if free_end <= free_start:
                    return jsonify({"error": "Free until must be after free from."}), 400
                cur.execute(
                    """
                    UPDATE room_members
                    SET budget_hard = %s,
                        budget_ideal = %s,
                        budget_currency = 'USD',
                        travel_limit_minutes = %s,
                        starting_area = %s,
                        free_start = %s,
                        free_end = %s,
                        ready = TRUE
                    WHERE room_id = %s AND user_id = %s
                    """,
                    (
                        budget_hard,
                        budget_ideal,
                        travel_limit,
                        starting_area,
                        free_start,
                        free_end,
                        room["room_id"],
                        user_id,
                    ),
                )
                if cur.rowcount != 1:
                    return jsonify({"error": "You are not in this room."}), 404
                payload = room_payload(cur, code, user_id)
    except errors.UndefinedTable:
        return jsonify({"error": "Tables are missing. Run python load_data.py once."}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(payload)


@app.get("/api/rooms/<code>")
def get_room(code):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                payload = room_payload(cur, code.strip().upper())
    except errors.UndefinedTable:
        return jsonify({"error": "Tables are missing. Run python load_data.py once."}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503
    if payload is None:
        return jsonify({"error": "No room with that code."}), 404
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
