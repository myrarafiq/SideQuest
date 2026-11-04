"""Bare Side Quest skeleton: one HTML page, a few Flask routes, Railway Postgres."""

import os
import secrets
import string
from pathlib import Path

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
    if "railway.internal" in url:
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


def room_payload(cur, code):
    cur.execute(
        """
        SELECT room_id, name, code, status, created_at
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
        SELECT u.name, m.role, m.ready
        FROM room_members m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.room_id = %s
        ORDER BY m.role DESC, u.name
        """,
        (room["room_id"],),
    )
    members = [
        {"name": row["name"], "role": row["role"], "ready": row["ready"]}
        for row in cur.fetchall()
    ]
    return {
        "name": room["name"],
        "code": room["code"],
        "status": room["status"],
        "members": members,
    }


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
                    VALUES (%s, %s, 'organizer', TRUE)
                    """,
                    (room_id, user_id),
                )
                payload = room_payload(cur, code)
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
                payload = room_payload(cur, code)
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
