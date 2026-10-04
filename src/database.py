"""SQLite database persistence layer for Hotel Information, Coordinates, and Prediction History.

Provides zero-dependency, local ACID storage for:
1. Hotel & Merchant Profile (single-tenant configuration with GPS coordinates and city presets).
2. Historical order predictions log (single & batch predictions with timestamps and GPS drop-off coordinates).
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

def resolve_database_path() -> str:
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return env_path

    # In serverless environments like Vercel, the repository root filesystem is read-only.
    # We automatically use the writable /tmp partition and seed it from bundled data if present.
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = "/tmp/delivery_platform.db"
        bundled_db = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "delivery_platform.db",
        )
        if os.path.exists(bundled_db) and not os.path.exists(tmp_db):
            try:
                import shutil
                shutil.copy2(bundled_db, tmp_db)
            except Exception:
                pass
        return tmp_db

    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "delivery_platform.db",
    )


DEFAULT_DB_PATH = resolve_database_path()


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a configured connection to the SQLite database."""
    target_path = db_path or resolve_database_path()
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn



def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if tables do not exist and applies non-destructive column migrations."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hotel_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    hotel_name TEXT NOT NULL,
                    branch_or_address TEXT DEFAULT '',
                    contact_email TEXT DEFAULT '',
                    contact_phone TEXT DEFAULT '',
                    default_prep_time_min REAL DEFAULT 15.0,
                    default_vehicle_type TEXT DEFAULT 'Scooter',
                    latitude REAL DEFAULT 40.7306,
                    longitude REAL DEFAULT -73.9866,
                    city_preset TEXT DEFAULT 'New York',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_reference TEXT,
                    distance_km REAL NOT NULL,
                    weather TEXT NOT NULL,
                    traffic_level TEXT NOT NULL,
                    time_of_day TEXT NOT NULL,
                    vehicle_type TEXT NOT NULL,
                    prep_time_min REAL NOT NULL,
                    courier_exp_yrs REAL NOT NULL,
                    predicted_time_min REAL NOT NULL,
                    risk_status TEXT NOT NULL,
                    source_type TEXT DEFAULT 'single',
                    destination_address TEXT DEFAULT '',
                    dropoff_lat REAL,
                    dropoff_lng REAL,
                    created_at TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_created 
                ON predictions_history(created_at DESC);
            """)

            # Safe column migration checks for pre-existing databases
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hotel_profile);")
            existing_hotel_cols = {col["name"] for col in cursor.fetchall()}
            if "latitude" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN latitude REAL DEFAULT 40.7306;")
            if "longitude" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN longitude REAL DEFAULT -73.9866;")
            if "city_preset" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN city_preset TEXT DEFAULT 'New York';")
            if "password_hash" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN password_hash TEXT DEFAULT '';")
            if "has_custom_model" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN has_custom_model INTEGER DEFAULT 0;")
            if "model_mae" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN model_mae REAL;")
            if "training_samples" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN training_samples INTEGER DEFAULT 0;")
            if "trained_at" not in existing_hotel_cols:
                conn.execute("ALTER TABLE hotel_profile ADD COLUMN trained_at TEXT DEFAULT '';")

            cursor.execute("PRAGMA table_info(predictions_history);")
            existing_pred_cols = {col["name"] for col in cursor.fetchall()}
            if "destination_address" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN destination_address TEXT DEFAULT '';")
            if "dropoff_lat" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN dropoff_lat REAL;")
            if "dropoff_lng" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN dropoff_lng REAL;")

            # -------------------------------------------------------------
            # Riders Fleet Table
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS riders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rider_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    vehicle_type TEXT DEFAULT 'Scooter',
                    courier_exp_yrs REAL DEFAULT 2.0,
                    rating REAL DEFAULT 4.8,
                    status TEXT DEFAULT 'Available',
                    current_lat REAL DEFAULT 0.0,
                    current_lng REAL DEFAULT 0.0,
                    current_address TEXT DEFAULT '',
                    last_active_at TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_riders_status 
                ON riders(status);
            """)

            # Seed initial realistic fleet if table is brand new
            cursor.execute("SELECT COUNT(*) AS total FROM riders;")
            r_count = cursor.fetchone()["total"]
            if r_count == 0:
                cursor.execute("SELECT latitude, longitude, branch_or_address FROM hotel_profile WHERE id = 1;")
                h_row = cursor.fetchone()
                h_lat = float(h_row["latitude"]) if h_row and h_row["latitude"] else 24.8385
                h_lng = float(h_row["longitude"]) if h_row and h_row["longitude"] else 67.0810
                h_area = str(h_row["branch_or_address"] if h_row and h_row["branch_or_address"] else "Local District")

                now_ts = datetime.now().isoformat()
                demo_riders = [
                    ("Tariq Khan", "+92 300 1234567", "Scooter", 3.5, 4.9, "Available", round(h_lat + 0.007, 6), round(h_lng + 0.005, 6), f"Near {h_area}"),
                    ("Ali Raza", "+92 321 9876543", "Scooter", 2.0, 4.7, "On Delivery", round(h_lat + 0.014, 6), round(h_lng + 0.011, 6), f"En Route from {h_area}"),
                    ("Usman Ahmed", "+92 333 4567890", "Car", 5.0, 5.0, "Available", round(h_lat - 0.009, 6), round(h_lng - 0.007, 6), f"Station Hub, {h_area}"),
                    ("Bilal Shah", "+92 345 6789012", "Bike", 1.5, 4.6, "Offline", round(h_lat + 0.002, 6), round(h_lng - 0.003, 6), f"Rest Point, {h_area}"),
                ]
                for name, ph, veh, exp, rat, stat, r_lat, r_lng, r_addr in demo_riders:
                    conn.execute("""
                        INSERT INTO riders (
                            rider_name, phone, vehicle_type, courier_exp_yrs, rating,
                            status, current_lat, current_lng, current_address,
                            last_active_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (name, ph, veh, exp, rat, stat, r_lat, r_lng, r_addr, now_ts, now_ts, now_ts))
    finally:
        conn.close()


def get_hotel_profile(db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the configured hotel profile, or None if not yet configured."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hotel_profile WHERE id = 1 LIMIT 1;")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


import hashlib


def hash_password(password: str) -> str:
    """Computes a salted SHA-256 hash for secure password storage."""
    if not password:
        return ""
    return hashlib.sha256(f"dtml_{password}_salt".encode("utf-8")).hexdigest()


def save_or_update_hotel_profile(
    profile_data: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserts or updates the single hotel profile in SQLite."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()

    hotel_name = str(profile_data.get("hotel_name", "")).strip() or "My Hotel / Restaurant"
    branch_or_address = str(profile_data.get("branch_or_address", "")).strip()
    contact_email = str(profile_data.get("contact_email", "")).strip()
    contact_phone = str(profile_data.get("contact_phone", "")).strip()
    default_prep_time = float(profile_data.get("default_prep_time_min", 15.0))
    default_vehicle = str(profile_data.get("default_vehicle_type", "Scooter")).strip()
    latitude = float(profile_data.get("latitude", 40.7306))
    longitude = float(profile_data.get("longitude", -73.9866))
    city_preset = str(profile_data.get("city_preset", "New York")).strip()

    # Password hashing support
    password_hash = str(profile_data.get("password_hash", "")).strip()
    if not password_hash and profile_data.get("password"):
        password_hash = hash_password(str(profile_data["password"]))

    has_custom_model = int(bool(profile_data.get("has_custom_model", 0)))
    model_mae = profile_data.get("model_mae")
    if model_mae is not None:
        try:
            model_mae = float(model_mae)
        except (ValueError, TypeError):
            model_mae = None
    training_samples = int(profile_data.get("training_samples", 0))
    trained_at = str(profile_data.get("trained_at", "")).strip()

    try:
        with conn:
            conn.execute("""
                INSERT INTO hotel_profile (
                    id, hotel_name, branch_or_address, contact_email, contact_phone,
                    default_prep_time_min, default_vehicle_type, latitude, longitude,
                    city_preset, password_hash, has_custom_model, model_mae,
                    training_samples, trained_at, created_at, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    hotel_name = excluded.hotel_name,
                    branch_or_address = excluded.branch_or_address,
                    contact_email = excluded.contact_email,
                    contact_phone = excluded.contact_phone,
                    default_prep_time_min = excluded.default_prep_time_min,
                    default_vehicle_type = excluded.default_vehicle_type,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    city_preset = excluded.city_preset,
                    password_hash = CASE WHEN excluded.password_hash != '' THEN excluded.password_hash ELSE hotel_profile.password_hash END,
                    has_custom_model = excluded.has_custom_model,
                    model_mae = excluded.model_mae,
                    training_samples = excluded.training_samples,
                    trained_at = excluded.trained_at,
                    updated_at = excluded.updated_at;
            """, (
                hotel_name,
                branch_or_address,
                contact_email,
                contact_phone,
                default_prep_time,
                default_vehicle,
                latitude,
                longitude,
                city_preset,
                password_hash,
                has_custom_model,
                model_mae,
                training_samples,
                trained_at,
                now_iso,
                now_iso,
            ))
        return get_hotel_profile(db_path) or {}
    finally:
        conn.close()


def log_prediction(
    order_dict: Dict[str, Any],
    predicted_time: float,
    risk_status: Optional[str] = None,
    source_type: str = "single",
    order_reference: Optional[str] = None,
    destination_address: Optional[str] = None,
    dropoff_lat: Optional[float] = None,
    dropoff_lng: Optional[float] = None,
    db_path: Optional[str] = None,
) -> int:
    """Logs an individual prediction record into SQLite history."""
    init_db(db_path)

    if not risk_status:
        if predicted_time <= 35:
            risk_status = "Fast / Low Risk"
        elif predicted_time <= 50:
            risk_status = "Standard / Medium Risk"
        else:
            risk_status = "High Delay Risk"

    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions_history (
                    order_reference, distance_km, weather, traffic_level, time_of_day,
                    vehicle_type, prep_time_min, courier_exp_yrs, predicted_time_min,
                    risk_status, source_type, destination_address, dropoff_lat, dropoff_lng, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                order_reference,
                float(order_dict.get("Distance_km", 0.0)),
                str(order_dict.get("Weather", "Clear")),
                str(order_dict.get("Traffic_Level", "Medium")),
                str(order_dict.get("Time_of_Day", "Evening")),
                str(order_dict.get("Vehicle_Type", "Scooter")),
                float(order_dict.get("Preparation_Time_min", 15.0)),
                float(order_dict.get("Courier_Experience_yrs", 3.0)),
                round(float(predicted_time), 2),
                risk_status,
                source_type,
                str(destination_address or order_dict.get("Destination_Address", "") or "").strip(),
                dropoff_lat if dropoff_lat is not None else order_dict.get("Dropoff_Lat"),
                dropoff_lng if dropoff_lng is not None else order_dict.get("Dropoff_Lng"),
                now_iso,
            ))
            return cursor.lastrowid or 0
    finally:
        conn.close()


def get_recent_predictions(
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves recent predictions ordered from newest to oldest."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM predictions_history 
            ORDER BY id DESC 
            LIMIT ? OFFSET ?;
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_predictions_count(db_path: Optional[str] = None) -> int:
    """Returns the total number of logged predictions in SQLite."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM predictions_history;")
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def clear_predictions_history(db_path: Optional[str] = None) -> int:
    """Clears all records from predictions_history table."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM predictions_history;")
            return cursor.rowcount
    finally:
        conn.close()


# ==============================================================================
# Rider & Fleet Persistence Methods
# ==============================================================================

def create_or_update_rider(
    rider_data: Dict[str, Any],
    rider_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new delivery rider or updates an existing rider in SQLite."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()

    name = str(rider_data.get("rider_name", "")).strip() or "Courier Partner"
    phone = str(rider_data.get("phone", "")).strip()
    vehicle = str(rider_data.get("vehicle_type", "Scooter")).strip()
    experience = float(rider_data.get("courier_exp_yrs", 2.0))
    rating = float(rider_data.get("rating", 4.8))
    status_val = str(rider_data.get("status", "Available")).strip()
    lat = float(rider_data.get("current_lat") or 0.0)
    lng = float(rider_data.get("current_lng") or 0.0)
    address = str(rider_data.get("current_address", "")).strip()

    try:
        with conn:
            cursor = conn.cursor()
            if rider_id:
                cursor.execute("""
                    UPDATE riders SET
                        rider_name = ?, phone = ?, vehicle_type = ?, courier_exp_yrs = ?,
                        rating = ?, status = ?, current_lat = ?, current_lng = ?,
                        current_address = ?, last_active_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (name, phone, vehicle, experience, rating, status_val, lat, lng, address, now_iso, now_iso, rider_id))
                target_id = rider_id
            else:
                cursor.execute("""
                    INSERT INTO riders (
                        rider_name, phone, vehicle_type, courier_exp_yrs, rating,
                        status, current_lat, current_lng, current_address,
                        last_active_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (name, phone, vehicle, experience, rating, status_val, lat, lng, address, now_iso, now_iso, now_iso))
                target_id = cursor.lastrowid

            cursor.execute("SELECT * FROM riders WHERE id = ?;", (target_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    finally:
        conn.close()


def get_all_riders(
    status_filter: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all registered delivery couriers, optionally filtered by status."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if status_filter and status_filter.lower() != "all":
            cursor.execute("""
                SELECT * FROM riders 
                WHERE LOWER(status) = LOWER(?)
                ORDER BY id ASC;
            """, (status_filter.strip(),))
        else:
            cursor.execute("SELECT * FROM riders ORDER BY id ASC;")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_rider_by_id(rider_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single rider by ID."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM riders WHERE id = ?;", (rider_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_rider_location(
    rider_id: int,
    lat: float,
    lng: float,
    address: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Updates a rider's live GPS coordinates and timestamp."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            cursor = conn.cursor()
            if address is not None:
                cursor.execute("""
                    UPDATE riders SET
                        current_lat = ?, current_lng = ?, current_address = ?,
                        last_active_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (lat, lng, address, now_iso, now_iso, rider_id))
            else:
                cursor.execute("""
                    UPDATE riders SET
                        current_lat = ?, current_lng = ?,
                        last_active_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (lat, lng, now_iso, now_iso, rider_id))
            cursor.execute("SELECT * FROM riders WHERE id = ?;", (rider_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def update_rider_status(
    rider_id: int,
    status_val: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Updates a rider's operational status (e.g. Available, On Delivery, Busy, Offline)."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE riders SET
                    status = ?, last_active_at = ?, updated_at = ?
                WHERE id = ?;
            """, (status_val.strip(), now_iso, now_iso, rider_id))
            cursor.execute("SELECT * FROM riders WHERE id = ?;", (rider_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_rider(rider_id: int, db_path: Optional[str] = None) -> bool:
    """Removes a rider from the database."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM riders WHERE id = ?;", (rider_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_fleet_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates real-time stats for the rider fleet."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM riders;")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS avail FROM riders WHERE LOWER(status) = 'available';")
        available = cursor.fetchone()["avail"]

        cursor.execute("SELECT COUNT(*) AS on_del FROM riders WHERE LOWER(status) = 'on delivery';")
        on_delivery = cursor.fetchone()["on_del"]

        cursor.execute("SELECT COUNT(*) AS offl FROM riders WHERE LOWER(status) = 'offline';")
        offline = cursor.fetchone()["offl"]

        cursor.execute("SELECT AVG(courier_exp_yrs) AS avg_exp FROM riders;")
        avg_exp_row = cursor.fetchone()
        avg_exp = round(float(avg_exp_row["avg_exp"]), 1) if avg_exp_row and avg_exp_row["avg_exp"] is not None else 0.0

        return {
            "total_riders": total,
            "available_riders": available,
            "on_delivery_riders": on_delivery,
            "offline_riders": offline,
            "avg_experience_yrs": avg_exp,
        }
    finally:
        conn.close()

