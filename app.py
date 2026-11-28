import os
import re
import sqlite3
import secrets
from datetime import date
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "autoglow.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("ALLOWED_ORIGINS", "https://gchiarg4-blip.github.io,http://127.0.0.1:5000,http://localhost:5000").split(",") if x.strip()]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

SERVICES = {
    "Basic Wash": 299,
    "Premium Wash": 599,
    "Interior Cleaning": 499,
    "Scratch Repair": 799,
    "Minor Dent Repair": 1499,
    "General Inspection": 399,
}
STATUSES = {"Pending", "Confirmed", "In Progress", "Completed", "Cancelled"}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY,
            customer TEXT NOT NULL,
            phone TEXT NOT NULL,
            vehicle TEXT NOT NULL,
            registration TEXT NOT NULL,
            service TEXT NOT NULL,
            price INTEGER NOT NULL,
            provider TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            created TEXT NOT NULL
        )
        """)

def row_to_dict(row):
    return dict(row)

@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/<path:filename>")
def static_files(filename):
    # Serve local frontend assets (if any); API routes are handled separately.
    target = BASE_DIR / filename
    if target.is_file() and BASE_DIR in target.resolve().parents:
        return send_from_directory(BASE_DIR, filename)
    return jsonify(error="File not found"), 404

@app.get("/api/health")
def health():
    return jsonify(status="ok", service="AutoGlow API")

@app.post("/api/bookings")
def create_booking():
    data = request.get_json(silent=True) or {}
    required = ["customer", "phone", "vehicle", "registration", "service", "provider", "date", "time"]
    missing = [key for key in required if not str(data.get(key, "")).strip()]
    if missing:
        return jsonify(error="Please complete all required booking fields."), 400

    service = str(data["service"]).strip()
    if service not in SERVICES:
        return jsonify(error="Please select a valid AutoGlow service."), 400
    booking_date = str(data["date"]).strip()
    try:
        parsed_date = date.fromisoformat(booking_date)
    except ValueError:
        return jsonify(error="Please provide a valid booking date (YYYY-MM-DD)."), 400
    if parsed_date < date.today():
        return jsonify(error="Booking date cannot be in the past."), 400

    phone = re.sub(r"[^0-9+]", "", str(data["phone"]))[:20]
    if len(re.sub(r"\D", "", phone)) < 7:
        return jsonify(error="Please provide a valid phone number."), 400

    booking = {
        "id": "AG-" + secrets.token_hex(5).upper(),
        "customer": str(data["customer"]).strip()[:100],
        "phone": phone,
        "vehicle": str(data["vehicle"]).strip()[:100],
        "registration": str(data["registration"]).strip().upper()[:20],
        "service": service,
        "price": SERVICES[service],
        "provider": str(data["provider"]).strip()[:100],
        "date": booking_date,
        "time": str(data["time"]).strip()[:30],
        "notes": str(data.get("notes", "")).strip()[:500],
        "status": "Pending",
        "created": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with db() as conn:
        # Retry if the short, human-friendly ID happens to collide.
        while conn.execute("SELECT 1 FROM bookings WHERE id=?", (booking["id"],)).fetchone():
            booking["id"] = "AG-" + secrets.token_hex(5).upper()
        conn.execute("""INSERT INTO bookings
        (id,customer,phone,vehicle,registration,service,price,provider,date,time,notes,status,created)
        VALUES (:id,:customer,:phone,:vehicle,:registration,:service,:price,:provider,:date,:time,:notes,:status,:created)""", booking)
    return jsonify(message="Booking created", booking=booking), 201

@app.get("/api/bookings")
def list_bookings():
    # Return only fields needed by the history screen; do not expose customer phone/name/notes.
    with db() as conn:
        rows = conn.execute("SELECT id,vehicle,service,price,provider,date,time,status,created FROM bookings ORDER BY created DESC").fetchall()
    return jsonify(bookings=[row_to_dict(row) for row in rows])

@app.get("/api/bookings/<booking_id>")
def get_booking(booking_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id.upper(),)).fetchone()
    if row is None:
        return jsonify(error="No booking found with that ID."), 404
    # Public tracking deliberately omits personal contact details and private notes.
    booking = {key: row[key] for key in ("id", "vehicle", "service", "price", "provider", "date", "time", "status", "created")}
    return jsonify(booking=booking)

@app.post("/api/bookings/<booking_id>/cancel")
def cancel_booking(booking_id):
    with db() as conn:
        row = conn.execute("SELECT status FROM bookings WHERE id=?", (booking_id.upper(),)).fetchone()
        if row is None:
            return jsonify(error="No booking found with that ID."), 404
        if row["status"] in ("Completed", "Cancelled"):
            return jsonify(error=f"This booking cannot be cancelled because its status is {row['status']}."), 409
        conn.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id.upper(),))
        updated = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id.upper(),)).fetchone()
    return jsonify(message="Booking cancelled", booking=row_to_dict(updated))

@app.patch("/api/bookings/<booking_id>/status")
def update_status(booking_id):
    # Protect status changes; set ADMIN_KEY in the hosting environment.
    expected = os.environ.get("ADMIN_KEY")
    supplied = request.headers.get("X-Admin-Key", "")
    if not expected or not secrets.compare_digest(supplied, expected):
        return jsonify(error="Admin authorization required."), 401
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in STATUSES:
        return jsonify(error="Invalid status. Use: " + ", ".join(sorted(STATUSES))), 400
    with db() as conn:
        cur = conn.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id.upper()))
        if cur.rowcount == 0:
            return jsonify(error="No booking found with that ID."), 404
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id.upper(),)).fetchone()
    return jsonify(message="Status updated", booking=row_to_dict(row))

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
