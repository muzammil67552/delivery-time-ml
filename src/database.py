"""SQLite database persistence layer for Hotel Information, Coordinates, and Prediction History.

Provides zero-dependency, local ACID storage for:
1. Hotel & Merchant Profile (single-tenant configuration with GPS coordinates and city presets).
2. Historical order predictions log (single & batch predictions with timestamps and GPS drop-off coordinates).
"""

import os
import sqlite3
import hashlib
import json
import math
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

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


_INITIALIZED_DBS: Dict[str, bool] = {}


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a configured connection to the SQLite database with WAL mode and concurrency timeout."""
    target_path = db_path or resolve_database_path()
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
    except Exception:
        pass
    return conn


def seed_hotel_riders(
    hotel_id: int,
    lat: float = 40.7306,
    lng: float = -73.9866,
    area: str = "Local Hub",
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Seeds 4 dedicated realistic courier riders for a specific hotel at its geographic coordinates."""
    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True

    try:
        cursor = active_conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM riders WHERE hotel_id = ?;", (hotel_id,))
        if cursor.fetchone()["total"] > 0:
            return  # Fleet already exists for this hotel

        now_ts = datetime.now().isoformat()
        area_clean = str(area).strip() if area else "Dispatch Hub"
        base_lat = float(lat) if lat else 40.7306
        base_lng = float(lng) if lng else -73.9866

        demo_riders = [
            ("Tariq Khan", "+92 300 1234567", "tariq.courier@example.com", "Scooter", 3.5, 4.9, "Available", round(base_lat + 0.007, 6), round(base_lng + 0.005, 6), f"Near {area_clean}", 18, 17, 94.4),
            ("Ali Raza", "+92 321 9876543", "ali.courier@example.com", "Scooter", 2.0, 4.7, "On Delivery", round(base_lat + 0.014, 6), round(base_lng + 0.011, 6), f"En Route from {area_clean}", 12, 11, 91.7),
            ("Usman Ahmed", "+92 333 4567890", "usman.courier@example.com", "Car", 5.0, 5.0, "Available", round(base_lat - 0.009, 6), round(base_lng - 0.007, 6), f"Station Hub, {area_clean}", 25, 25, 100.0),
            ("Bilal Shah", "+92 345 6789012", "bilal.courier@example.com", "Bike", 1.5, 4.6, "Offline", round(base_lat + 0.002, 6), round(base_lng - 0.003, 6), f"Rest Point, {area_clean}", 8, 7, 87.5),
        ]
        for name, ph, em, veh, exp, rat, stat, r_lat, r_lng, r_addr, tot, ont, perf in demo_riders:
            active_conn.execute("""
                INSERT INTO riders (
                    hotel_id, rider_name, phone, email, vehicle_type, courier_exp_yrs, rating,
                    status, current_lat, current_lng, current_address,
                    total_deliveries, on_time_deliveries, performance_score,
                    last_active_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (hotel_id, name, ph, em, veh, exp, rat, stat, r_lat, r_lng, r_addr, tot, ont, perf, now_ts, now_ts, now_ts))
    finally:
        if should_close:
            active_conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if tables do not exist and applies non-destructive multi-tenant migrations."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()

            # -------------------------------------------------------------
            # 1. Hotel Profile Schema & Migration (remove CHECK (id = 1))
            # -------------------------------------------------------------
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='hotel_profile';")
            master_row = cursor.fetchone()
            if master_row and master_row["sql"] and ("CHECK (id = 1)" in master_row["sql"] or "CHECK(id = 1)" in master_row["sql"] or "CHECK (id=1)" in master_row["sql"]):
                # Migrate single-tenant table to multi-tenant AUTOINCREMENT table
                conn.execute("ALTER TABLE hotel_profile RENAME TO hotel_profile_legacy;")
                conn.execute("""
                    CREATE TABLE hotel_profile (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hotel_name TEXT NOT NULL,
                        branch_or_address TEXT DEFAULT '',
                        contact_email TEXT DEFAULT '',
                        contact_phone TEXT DEFAULT '',
                        default_prep_time_min REAL DEFAULT 15.0,
                        default_vehicle_type TEXT DEFAULT 'Scooter',
                        latitude REAL DEFAULT 40.7306,
                        longitude REAL DEFAULT -73.9866,
                        city_preset TEXT DEFAULT 'New York',
                        password_hash TEXT DEFAULT '',
                        has_custom_model INTEGER DEFAULT 0,
                        model_mae REAL,
                        training_samples INTEGER DEFAULT 0,
                        trained_at TEXT DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                cursor.execute("PRAGMA table_info(hotel_profile_legacy);")
                legacy_cols = {col["name"] for col in cursor.fetchall()}
                target_cols = [
                    "id", "hotel_name", "branch_or_address", "contact_email", "contact_phone",
                    "default_prep_time_min", "default_vehicle_type", "latitude", "longitude",
                    "city_preset", "password_hash", "has_custom_model", "model_mae",
                    "training_samples", "trained_at", "created_at", "updated_at"
                ]
                common_cols = [c for c in target_cols if c in legacy_cols]
                if common_cols:
                    cols_str = ", ".join(common_cols)
                    conn.execute(f"INSERT INTO hotel_profile ({cols_str}) SELECT {cols_str} FROM hotel_profile_legacy;")
                conn.execute("DROP TABLE hotel_profile_legacy;")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS hotel_profile (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hotel_name TEXT NOT NULL,
                        branch_or_address TEXT DEFAULT '',
                        contact_email TEXT DEFAULT '',
                        contact_phone TEXT DEFAULT '',
                        default_prep_time_min REAL DEFAULT 15.0,
                        default_vehicle_type TEXT DEFAULT 'Scooter',
                        latitude REAL DEFAULT 40.7306,
                        longitude REAL DEFAULT -73.9866,
                        city_preset TEXT DEFAULT 'New York',
                        password_hash TEXT DEFAULT '',
                        has_custom_model INTEGER DEFAULT 0,
                        model_mae REAL,
                        training_samples INTEGER DEFAULT 0,
                        trained_at TEXT DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

            # Column verification on hotel_profile
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

            # -------------------------------------------------------------
            # 2. Predictions History Table & multi-tenant hotel_id migration
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER DEFAULT 1,
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

            cursor.execute("PRAGMA table_info(predictions_history);")
            existing_pred_cols = {col["name"] for col in cursor.fetchall()}
            if "hotel_id" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN hotel_id INTEGER DEFAULT 1;")
            if "destination_address" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN destination_address TEXT DEFAULT '';")
            if "dropoff_lat" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN dropoff_lat REAL;")
            if "dropoff_lng" not in existing_pred_cols:
                conn.execute("ALTER TABLE predictions_history ADD COLUMN dropoff_lng REAL;")

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_created 
                ON predictions_history(created_at DESC);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_hotel 
                ON predictions_history(hotel_id);
            """)

            # -------------------------------------------------------------
            # 3. Riders Fleet Table & multi-tenant hotel_id migration
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS riders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER DEFAULT 1,
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

            cursor.execute("PRAGMA table_info(riders);")
            existing_rider_cols = {col["name"] for col in cursor.fetchall()}
            if "hotel_id" not in existing_rider_cols:
                conn.execute("ALTER TABLE riders ADD COLUMN hotel_id INTEGER DEFAULT 1;")
            if "email" not in existing_rider_cols:
                conn.execute("ALTER TABLE riders ADD COLUMN email TEXT DEFAULT '';")
            if "total_deliveries" not in existing_rider_cols:
                conn.execute("ALTER TABLE riders ADD COLUMN total_deliveries INTEGER DEFAULT 0;")
            if "on_time_deliveries" not in existing_rider_cols:
                conn.execute("ALTER TABLE riders ADD COLUMN on_time_deliveries INTEGER DEFAULT 0;")
            if "performance_score" not in existing_rider_cols:
                conn.execute("ALTER TABLE riders ADD COLUMN performance_score REAL DEFAULT 100.0;")

            # Backfill any existing couriers missing an email
            conn.execute("""
                UPDATE riders 
                SET email = LOWER(REPLACE(rider_name, ' ', '.')) || '@example.com' 
                WHERE email IS NULL OR email = '';
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_riders_status 
                ON riders(status);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_riders_hotel 
                ON riders(hotel_id);
            """)

            # -------------------------------------------------------------
            # 4. Dispatch Orders & Cascading Pipeline Schema
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER DEFAULT 1,
                    tracking_id TEXT UNIQUE NOT NULL,
                    client_name TEXT NOT NULL,
                    client_phone TEXT NOT NULL,
                    client_address TEXT NOT NULL,
                    dest_lat REAL,
                    dest_lng REAL,
                    distance_km REAL NOT NULL,
                    weather TEXT NOT NULL,
                    traffic_level TEXT DEFAULT 'Medium',
                    time_of_day TEXT NOT NULL,
                    vehicle_type TEXT DEFAULT 'Scooter',
                    prep_time_min REAL DEFAULT 15.0,
                    courier_exp_yrs REAL DEFAULT 2.0,
                    predicted_eta_min REAL NOT NULL,
                    assigned_rider_id INTEGER,
                    rider_name TEXT,
                    rider_email TEXT,
                    dispatch_status TEXT DEFAULT 'Pending_Rider',
                    dispatch_attempts INTEGER DEFAULT 1,
                    notified_rider_ids TEXT DEFAULT '',
                    dispatch_token TEXT,
                    token_expires_at TEXT,
                    activated_at TEXT,
                    completed_at TEXT,
                    actual_duration_min REAL,
                    was_on_time INTEGER,
                    raw_payload_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dispatch_tracking 
                ON dispatch_orders(tracking_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dispatch_hotel 
                ON dispatch_orders(hotel_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dispatch_token 
                ON dispatch_orders(dispatch_token);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dispatch_status 
                ON dispatch_orders(dispatch_status);
            """)

            # -------------------------------------------------------------
            # 5. Dispatch Events Audit Trail (for ML Feature Logging)
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_events_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dispatch_order_id INTEGER NOT NULL,
                    tracking_id TEXT NOT NULL,
                    rider_id INTEGER,
                    event_type TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # -------------------------------------------------------------
            # 6. Dispatch Email Notification Log (HTML template previews)
            # -------------------------------------------------------------
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_id TEXT NOT NULL,
                    rider_id INTEGER,
                    recipient_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    html_body TEXT NOT NULL,
                    status TEXT DEFAULT 'SENT',
                    action_token TEXT,
                    sent_at TEXT NOT NULL
                );
            """)

            # -------------------------------------------------------------
            # 7. Kitchen Queue Schema & Indexes
            # -------------------------------------------------------------
            from src.kitchen import init_kitchen_tables
            init_kitchen_tables(conn)

            # Seed initial fleet for existing hotel if table is empty
            cursor.execute("SELECT COUNT(*) AS total FROM riders;")
            r_count = cursor.fetchone()["total"]
            if r_count == 0:
                cursor.execute("SELECT id, latitude, longitude, branch_or_address FROM hotel_profile ORDER BY id ASC LIMIT 1;")
                h_row = cursor.fetchone()
                h_id = h_row["id"] if h_row else 1
                h_lat = float(h_row["latitude"]) if h_row and h_row["latitude"] else 40.7306
                h_lng = float(h_row["longitude"]) if h_row and h_row["longitude"] else -73.9866
                h_area = str(h_row["branch_or_address"] if h_row and h_row["branch_or_address"] else "Local District")
                seed_hotel_riders(hotel_id=h_id, lat=h_lat, lng=h_lng, area=h_area, conn=conn)
    finally:
        conn.close()


def get_hotel_profile(hotel_id: Optional[int] = None, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the configured hotel profile by specific ID, or the most recently active profile."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if hotel_id is not None:
            cursor.execute("SELECT * FROM hotel_profile WHERE id = ? LIMIT 1;", (hotel_id,))
        else:
            cursor.execute("SELECT * FROM hotel_profile ORDER BY updated_at DESC, id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """Computes a salted SHA-256 hash for secure password storage."""
    if not password:
        return ""
    return hashlib.sha256(f"dtml_{password}_salt".encode("utf-8")).hexdigest()


def authenticate_hotel(
    hotel_name: str,
    email: str,
    password: str,
    db_path: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Validates hotel manager credentials against registered accounts in SQLite."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        clean_hotel = str(hotel_name or "").strip().lower()
        clean_email = str(email or "").strip().lower()

        # 1. Search for matching record by email and hotel name
        cursor.execute("""
            SELECT * FROM hotel_profile 
            WHERE LOWER(TRIM(contact_email)) = ? AND LOWER(TRIM(hotel_name)) = ?
            ORDER BY id DESC LIMIT 1;
        """, (clean_email, clean_hotel))
        row = cursor.fetchone()

        # 2. If not found by both, search by email alone
        if not row:
            cursor.execute("""
                SELECT * FROM hotel_profile 
                WHERE LOWER(TRIM(contact_email)) = ?
                ORDER BY id DESC LIMIT 1;
            """, (clean_email,))
            row = cursor.fetchone()

        # 3. If not found by email, search by hotel name alone
        if not row:
            cursor.execute("""
                SELECT * FROM hotel_profile 
                WHERE LOWER(TRIM(hotel_name)) = ?
                ORDER BY id DESC LIMIT 1;
            """, (clean_hotel,))
            row = cursor.fetchone()

        if not row:
            return False, "No hotel account found matching these credentials. Please check your hotel name and email.", None

        profile = dict(row)
        stored_hotel = str(profile.get("hotel_name", "")).strip()
        stored_email = str(profile.get("contact_email", "")).strip()
        stored_hash = str(profile.get("password_hash", "")).strip()

        # Compare hotel name (case-insensitive)
        if clean_hotel != stored_hotel.lower():
            return False, f"Hotel '{hotel_name.strip()}' does not match registered hotel '{stored_hotel}'.", None

        # Compare email (case-insensitive)
        if clean_email != stored_email.lower():
            return False, f"Email '{email.strip()}' does not match the registered owner email.", None

        # Compare password
        if stored_hash:
            input_hash = hash_password(password)
            if input_hash != stored_hash:
                return False, "Incorrect password. Please verify your credentials and try again.", None
        else:
            # If the profile didn't have password set yet, set it now
            new_hash = hash_password(password)
            with conn:
                conn.execute("UPDATE hotel_profile SET password_hash = ? WHERE id = ?;", (new_hash, profile["id"]))
            profile["password_hash"] = new_hash

        # Update updated_at so this account becomes the active session
        now_iso = datetime.now().isoformat()
        with conn:
            conn.execute("UPDATE hotel_profile SET updated_at = ? WHERE id = ?;", (now_iso, profile["id"]))
        profile["updated_at"] = now_iso

        # Return profile without sensitive password hash
        safe_profile = dict(profile)
        safe_profile.pop("password_hash", None)
        return True, f"Welcome back to {stored_hotel}!", safe_profile
    finally:
        conn.close()


def save_or_update_hotel_profile(
    profile_data: Dict[str, Any],
    force_new: bool = False,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserts or updates a hotel profile in SQLite.
    
    If force_new is True (e.g. from /api/register-hotel onboarding), a brand-new hotel
    profile is inserted with its own unique AUTOINCREMENT ID and its own dedicated courier fleet.
    If force_new is False, updates the specified profile or latest active profile.
    """
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
            cursor = conn.cursor()

            target_id = None
            if not force_new:
                if profile_data.get("id"):
                    target_id = int(profile_data["id"])
                elif contact_email:
                    cursor.execute("SELECT id FROM hotel_profile WHERE LOWER(TRIM(contact_email)) = LOWER(?) LIMIT 1;", (contact_email,))
                    row = cursor.fetchone()
                    if row:
                        target_id = row["id"]
                if target_id is None:
                    latest = get_hotel_profile(db_path=db_path)
                    if latest:
                        target_id = latest["id"]

            if target_id is not None and not force_new:
                # Update existing hotel record
                cursor.execute("""
                    UPDATE hotel_profile SET
                        hotel_name = ?,
                        branch_or_address = ?,
                        contact_email = ?,
                        contact_phone = ?,
                        default_prep_time_min = ?,
                        default_vehicle_type = ?,
                        latitude = ?,
                        longitude = ?,
                        city_preset = ?,
                        password_hash = CASE WHEN ? != '' THEN ? ELSE password_hash END,
                        has_custom_model = ?,
                        model_mae = ?,
                        training_samples = ?,
                        trained_at = ?,
                        updated_at = ?
                    WHERE id = ?;
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
                    password_hash,
                    has_custom_model,
                    model_mae,
                    training_samples,
                    trained_at,
                    now_iso,
                    target_id,
                ))
                saved_id = target_id
            else:
                # Insert brand-new hotel profile
                cursor.execute("""
                    INSERT INTO hotel_profile (
                        hotel_name, branch_or_address, contact_email, contact_phone,
                        default_prep_time_min, default_vehicle_type, latitude, longitude,
                        city_preset, password_hash, has_custom_model, model_mae,
                        training_samples, trained_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                saved_id = cursor.lastrowid
                # Seed fresh dedicated courier fleet for this new hotel profile
                seed_hotel_riders(saved_id, latitude, longitude, branch_or_address, conn=conn)

        return get_hotel_profile(hotel_id=saved_id, db_path=db_path) or {}
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
    hotel_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> int:
    """Logs an individual prediction record into SQLite history scoped by hotel_id."""
    init_db(db_path)

    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

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
                    hotel_id, order_reference, distance_km, weather, traffic_level, time_of_day,
                    vehicle_type, prep_time_min, courier_exp_yrs, predicted_time_min,
                    risk_status, source_type, destination_address, dropoff_lat, dropoff_lng, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                hotel_id,
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
    hotel_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves recent predictions ordered from newest to oldest for a specific hotel."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM predictions_history 
            WHERE hotel_id = ?
            ORDER BY id DESC 
            LIMIT ? OFFSET ?;
        """, (hotel_id, limit, offset))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_predictions_count(hotel_id: Optional[int] = None, db_path: Optional[str] = None) -> int:
    """Returns the total number of logged predictions in SQLite for a specific hotel."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM predictions_history WHERE hotel_id = ?;", (hotel_id,))
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        conn.close()


def clear_predictions_history(hotel_id: Optional[int] = None, db_path: Optional[str] = None) -> int:
    """Clears records from predictions_history table for a specific hotel."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM predictions_history WHERE hotel_id = ?;", (hotel_id,))
            return cursor.rowcount
    finally:
        conn.close()


# ==============================================================================
# Rider & Fleet Persistence Methods
# ==============================================================================

def create_or_update_rider(
    rider_data: Dict[str, Any],
    rider_id: Optional[int] = None,
    hotel_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new delivery rider or updates an existing rider in SQLite, scoped by hotel_id."""
    init_db(db_path)
    if hotel_id is None:
        hotel_id = rider_data.get("hotel_id")
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()

    name = str(rider_data.get("rider_name", "")).strip() or "Courier Partner"
    phone = str(rider_data.get("phone", "")).strip()
    email = str(rider_data.get("email", "")).strip()
    if not email and name:
        email = f"{name.lower().replace(' ', '.')}@example.com"
    vehicle = str(rider_data.get("vehicle_type", "Scooter")).strip()
    experience = float(rider_data.get("courier_exp_yrs", 2.0))
    rating = float(rider_data.get("rating", 4.8))
    status_val = str(rider_data.get("status", "Available")).strip()
    lat = float(rider_data.get("current_lat") or 0.0)
    lng = float(rider_data.get("current_lng") or 0.0)
    address = str(rider_data.get("current_address", "")).strip()
    total_del = int(rider_data.get("total_deliveries", 0))
    on_time_del = int(rider_data.get("on_time_deliveries", 0))
    perf_score = float(rider_data.get("performance_score", 100.0))

    try:
        with conn:
            cursor = conn.cursor()
            if rider_id:
                cursor.execute("""
                    UPDATE riders SET
                        rider_name = ?, phone = ?, email = ?, vehicle_type = ?, courier_exp_yrs = ?,
                        rating = ?, status = ?, current_lat = ?, current_lng = ?,
                        current_address = ?, total_deliveries = ?, on_time_deliveries = ?,
                        performance_score = ?, last_active_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (name, phone, email, vehicle, experience, rating, status_val, lat, lng, address, total_del, on_time_del, perf_score, now_iso, now_iso, rider_id))
                target_id = rider_id
            else:
                cursor.execute("""
                    INSERT INTO riders (
                        hotel_id, rider_name, phone, email, vehicle_type, courier_exp_yrs, rating,
                        status, current_lat, current_lng, current_address,
                        total_deliveries, on_time_deliveries, performance_score,
                        last_active_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (hotel_id, name, phone, email, vehicle, experience, rating, status_val, lat, lng, address, total_del, on_time_del, perf_score, now_iso, now_iso, now_iso))
                target_id = cursor.lastrowid

            cursor.execute("SELECT * FROM riders WHERE id = ?;", (target_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    finally:
        conn.close()


def get_all_riders(
    hotel_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all registered delivery couriers for a specific hotel, optionally filtered by status."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if status_filter and status_filter.lower() != "all":
            cursor.execute("""
                SELECT * FROM riders 
                WHERE hotel_id = ? AND LOWER(status) = LOWER(?)
                ORDER BY id ASC;
            """, (hotel_id, status_filter.strip()))
        else:
            cursor.execute("SELECT * FROM riders WHERE hotel_id = ? ORDER BY id ASC;", (hotel_id,))
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


def get_fleet_stats(hotel_id: Optional[int] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculates real-time stats for a specific hotel's rider fleet."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM riders WHERE hotel_id = ?;", (hotel_id,))
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS avail FROM riders WHERE hotel_id = ? AND LOWER(status) = 'available';", (hotel_id,))
        available = cursor.fetchone()["avail"]

        cursor.execute("SELECT COUNT(*) AS on_del FROM riders WHERE hotel_id = ? AND LOWER(status) = 'on delivery';", (hotel_id,))
        on_delivery = cursor.fetchone()["on_del"]

        cursor.execute("SELECT COUNT(*) AS offl FROM riders WHERE hotel_id = ? AND LOWER(status) = 'offline';", (hotel_id,))
        offline = cursor.fetchone()["offl"]

        cursor.execute("SELECT AVG(courier_exp_yrs) AS avg_exp FROM riders WHERE hotel_id = ?;", (hotel_id,))
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


# ==============================================================================
# Automated Dispatch Engine & Cascading Pipeline Methods
# ==============================================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great circle distance between two points in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    return 6371.0 * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))


def find_closest_available_rider(
    hotel_id: int,
    hotel_lat: float,
    hotel_lng: float,
    excluded_rider_ids: Optional[List[int]] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Finds the closest available courier to the hotel, prioritized by proximity and performance score."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    excluded = set(excluded_rider_ids or [])
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM riders 
            WHERE hotel_id = ? AND LOWER(status) = 'available'
            ORDER BY id ASC;
        """, (hotel_id,))
        candidates = [dict(row) for row in cursor.fetchall() if row["id"] not in excluded]
        if not candidates:
            return None

        ranked = []
        for r in candidates:
            r_lat = float(r.get("current_lat") or hotel_lat)
            r_lng = float(r.get("current_lng") or hotel_lng)
            dist_km = round(haversine_km(hotel_lat, hotel_lng, r_lat, r_lng), 2)
            perf = float(r.get("performance_score") or 100.0)
            rating = float(r.get("rating") or 4.8)
            # Effective score: lower is better. Higher performance and rating provide a distance bonus
            perf_boost = (perf / 100.0) * 0.25 + (rating / 5.0) * 0.15
            effective_dist = dist_km / (1.0 + perf_boost)
            r["distance_to_hotel_km"] = dist_km
            ranked.append((effective_dist, dist_km, r))

        ranked.sort(key=lambda x: x[0])
        return ranked[0][2]
    finally:
        conn.close()


def create_dispatch_order(order_data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """Persists a new dispatch order with auto-generated tracking ID, security token, and raw payload."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now()
    now_iso = now.isoformat()
    expires_iso = (now + timedelta(minutes=5)).isoformat()
    token = order_data.get("dispatch_token") or secrets.token_urlsafe(16)
    tracking_id = order_data.get("tracking_id")
    if not tracking_id:
        tracking_id = f"TRK-{secrets.token_hex(3).upper()}"

    hotel_id = int(order_data.get("hotel_id") or 1)

    client_name = str(order_data.get("client_name", "")).strip() or "Valued Customer"
    client_phone = str(order_data.get("client_phone", "")).strip() or "N/A"
    client_address = str(order_data.get("client_address", "")).strip()
    dest_lat = float(order_data.get("dest_lat") or 0.0)
    dest_lng = float(order_data.get("dest_lng") or 0.0)
    dist_km = float(order_data.get("distance_km") or 5.0)
    weather = str(order_data.get("weather", "Clear")).strip()
    traffic = str(order_data.get("traffic_level", "Medium")).strip()
    time_of_day = str(order_data.get("time_of_day", "Evening")).strip()
    vehicle = str(order_data.get("vehicle_type", "Scooter")).strip()
    prep_time = float(order_data.get("prep_time_min", 15.0))
    exp_yrs = float(order_data.get("courier_exp_yrs", 2.0))
    predicted_eta = float(order_data.get("predicted_eta_min", 25.0))

    assigned_rider_id = order_data.get("assigned_rider_id")
    rider_name = str(order_data.get("rider_name", "")).strip()
    rider_email = str(order_data.get("rider_email", "")).strip()
    dispatch_status = str(order_data.get("dispatch_status", "Pending_Rider")).strip()
    notified = order_data.get("notified_rider_ids", "")
    if isinstance(notified, list):
        notified = json.dumps(notified)

    raw_payload = order_data.get("raw_payload_json")
    if not raw_payload:
        raw_payload = json.dumps(order_data)

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dispatch_orders (
                    hotel_id, tracking_id, client_name, client_phone, client_address,
                    dest_lat, dest_lng, distance_km, weather, traffic_level, time_of_day,
                    vehicle_type, prep_time_min, courier_exp_yrs, predicted_eta_min,
                    assigned_rider_id, rider_name, rider_email, dispatch_status,
                    dispatch_attempts, notified_rider_ids, dispatch_token, token_expires_at,
                    raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                hotel_id, tracking_id, client_name, client_phone, client_address,
                dest_lat, dest_lng, dist_km, weather, traffic, time_of_day,
                vehicle, prep_time, exp_yrs, predicted_eta,
                assigned_rider_id, rider_name, rider_email, dispatch_status,
                int(order_data.get("dispatch_attempts", 1)), notified,
                token, expires_iso, raw_payload, now_iso, now_iso
            ))
            order_id = cursor.lastrowid

            # Log audit event
            cursor.execute("""
                INSERT INTO dispatch_events_log (
                    dispatch_order_id, tracking_id, rider_id, event_type, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (order_id, tracking_id, assigned_rider_id, "DISPATCH_TRIGGERED", json.dumps({"assigned_rider": rider_name}), now_iso))

            cursor.execute("SELECT * FROM dispatch_orders WHERE id = ?;", (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    finally:
        conn.close()


def get_dispatch_order_by_tracking_id(tracking_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a dispatch order by tracking ID."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dispatch_orders WHERE tracking_id = ? LIMIT 1;", (tracking_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_dispatch_order_by_token(token: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a dispatch order by its security dispatch token."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dispatch_orders WHERE dispatch_token = ? LIMIT 1;", (token.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def log_dispatch_event(
    dispatch_order_id: int,
    tracking_id: str,
    rider_id: Optional[int],
    event_type: str,
    details: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> None:
    """Logs an operational dispatch event for system auditing and ML data enrichment."""
    now_iso = datetime.now().isoformat()
    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True
    try:
        active_conn.execute("""
            INSERT INTO dispatch_events_log (
                dispatch_order_id, tracking_id, rider_id, event_type, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (dispatch_order_id, tracking_id, rider_id, event_type, json.dumps(details or {}), now_iso))
        if should_close:
            active_conn.commit()
    except Exception as exc:
        logger.warning(f"Could not log dispatch event: {exc}")
    finally:
        if should_close:
            active_conn.close()


def log_dispatch_email(
    tracking_id: str,
    rider_id: Optional[int],
    recipient_email: str,
    subject: str,
    html_body: str,
    status: str = "SENT",
    action_token: str = "",
    db_path: Optional[str] = None,
) -> int:
    """Logs a sent dispatch notification email with full HTML preview."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dispatch_email_logs (
                    tracking_id, rider_id, recipient_email, subject, html_body, status, action_token, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (tracking_id, rider_id, recipient_email, subject, html_body, status, action_token, now_iso))
            return cursor.lastrowid or 0
    finally:
        conn.close()


def get_email_logs_for_order(tracking_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all dispatch emails sent for a specific order tracking ID."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dispatch_email_logs WHERE tracking_id = ? ORDER BY id DESC;", (tracking_id.strip(),))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def activate_dispatch_order(token: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Action: Rider clicks 'Activate Order' from their notification email.
    
    Validates token, verifies 5-minute timeout window, marks order Active / In Transit,
    and updates courier status to 'On Delivery'.
    """
    order = get_dispatch_order_by_token(token, db_path=db_path)
    if not order:
        return {"success": False, "error": "Invalid or expired dispatch invitation link."}

    current_status = order.get("dispatch_status")
    if current_status == "Active":
        rider = get_rider_by_id(order["assigned_rider_id"], db_path=db_path) if order.get("assigned_rider_id") else None
        return {"success": True, "already_active": True, "order": order, "rider": rider}

    if current_status not in ("Pending_Rider", None):
        return {"success": False, "error": f"This order has already been {current_status.lower()}."}

    # Verify 5-minute expiry timeout
    expires_at_str = order.get("token_expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() > expires_at:
                # Expired! Auto-trigger cascading fallback to next rider
                cascade_res = deactivate_and_cascade_dispatch_order(token, reason="5_minute_timeout", db_path=db_path)
                return {
                    "success": False,
                    "error": "This order invitation expired after 5 minutes and has been automatically cascaded to another courier.",
                    "expired": True,
                    "cascade_result": cascade_res,
                }
        except Exception:
            pass

    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dispatch_orders SET
                    dispatch_status = 'Active',
                    activated_at = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (now_iso, now_iso, order["id"]))

            if order.get("assigned_rider_id"):
                cursor.execute("""
                    UPDATE riders SET
                        status = 'On Delivery',
                        last_active_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (now_iso, now_iso, order["assigned_rider_id"]))

            # Log audit event with current connection
            log_dispatch_event(
                dispatch_order_id=order["id"],
                tracking_id=order["tracking_id"],
                rider_id=order.get("assigned_rider_id"),
                event_type="ORDER_ACTIVATED",
                details={"rider_name": order.get("rider_name"), "activated_at": now_iso},
                conn=conn
            )
    finally:
        conn.close()

    updated = get_dispatch_order_by_tracking_id(order["tracking_id"], db_path=db_path)
    rider = get_rider_by_id(order["assigned_rider_id"], db_path=db_path) if order.get("assigned_rider_id") else None
    return {"success": True, "order": updated, "rider": rider}



def deactivate_and_cascade_dispatch_order(
    token: str,
    reason: str = "rider_declined",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Action: Rider clicks 'Deactivate Order' or 5-minute timeout expires.
    
    Drops current courier, adds to notified exclusion list, finds the NEXT closest available rider
    to the hotel, generates a fresh 5-minute token, and repeats the email dispatch pipeline.
    """
    init_db(db_path)
    order = get_dispatch_order_by_token(token, db_path=db_path)
    if not order:
        return {"success": False, "error": "Invalid dispatch order token."}

    if order.get("dispatch_status") == "Active":
        return {"success": False, "error": "Order has already been activated and is currently in transit."}

    old_rider_id = order.get("assigned_rider_id")
    hotel_id = order.get("hotel_id", 1)

    # Parse already notified riders
    notified_str = order.get("notified_rider_ids", "")
    try:
        notified_list = json.loads(notified_str) if notified_str else []
    except Exception:
        notified_list = [int(x) for x in notified_str.split(",") if x.strip().isdigit()]

    if old_rider_id and old_rider_id not in notified_list:
        notified_list.append(old_rider_id)

    # Retrieve hotel origin coordinates
    hotel_profile = get_hotel_profile(hotel_id=hotel_id, db_path=db_path) or {}
    h_lat = float(hotel_profile.get("latitude") or 40.7306)
    h_lng = float(hotel_profile.get("longitude") or -73.9866)

    # Search for next closest available courier to hotel
    next_rider = find_closest_available_rider(
        hotel_id=hotel_id,
        hotel_lat=h_lat,
        hotel_lng=h_lng,
        excluded_rider_ids=notified_list,
        db_path=db_path
    )

    conn = get_db_connection(db_path)
    now = datetime.now()
    now_iso = now.isoformat()

    try:
        with conn:
            cursor = conn.cursor()
            if next_rider:
                # Cascade to next rider
                new_token = secrets.token_urlsafe(16)
                new_expires_iso = (now + timedelta(minutes=5)).isoformat()
                new_attempts = int(order.get("dispatch_attempts", 1)) + 1

                cursor.execute("""
                    UPDATE dispatch_orders SET
                        assigned_rider_id = ?,
                        rider_name = ?,
                        rider_email = ?,
                        dispatch_status = 'Pending_Rider',
                        dispatch_attempts = ?,
                        notified_rider_ids = ?,
                        dispatch_token = ?,
                        token_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    next_rider["id"],
                    next_rider["rider_name"],
                    next_rider.get("email", ""),
                    new_attempts,
                    json.dumps(notified_list),
                    new_token,
                    new_expires_iso,
                    now_iso,
                    order["id"]
                ))

                log_dispatch_event(
                    dispatch_order_id=order["id"],
                    tracking_id=order["tracking_id"],
                    rider_id=old_rider_id,
                    event_type="ORDER_DEACTIVATED" if reason == "rider_declined" else "TIMEOUT_EXPIRED",
                    details={"dropped_rider": old_rider_id, "cascaded_to": next_rider["id"], "reason": reason},
                    conn=conn
                )

                cascade_result = {
                    "success": True,
                    "cascaded": True,
                    "reason": reason,
                    "old_rider_id": old_rider_id,
                    "next_rider": next_rider,
                }
            else:
                # No more available couriers
                cursor.execute("""
                    UPDATE dispatch_orders SET
                        dispatch_status = 'Unassigned_No_Riders',
                        notified_rider_ids = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (json.dumps(notified_list), now_iso, order["id"]))

                log_dispatch_event(
                    dispatch_order_id=order["id"],
                    tracking_id=order["tracking_id"],
                    rider_id=old_rider_id,
                    event_type="CASCADE_EXHAUSTED",
                    details={"message": "All couriers notified or unavailable", "reason": reason},
                    conn=conn
                )

                cascade_result = {
                    "success": True,
                    "cascaded": False,
                    "reason": "All active fleet couriers have declined or timed out.",
                }
    finally:
        try:
            conn.close()
        except Exception:
            pass

    updated = get_dispatch_order_by_tracking_id(order["tracking_id"], db_path=db_path)
    cascade_result["order"] = updated
    return cascade_result




def check_and_expire_timeout_dispatches(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Checks for orders pending courier response older than 5 minutes and auto-cascades them."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    now_iso = datetime.now().isoformat()
    timed_out_tokens = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dispatch_token FROM dispatch_orders
            WHERE dispatch_status = 'Pending_Rider'
              AND token_expires_at IS NOT NULL
              AND token_expires_at <= ?;
        """, (now_iso,))
        timed_out_tokens = [row["dispatch_token"] for row in cursor.fetchall() if row["dispatch_token"]]
    finally:
        conn.close()

    results = []
    for token in timed_out_tokens:
        res = deactivate_and_cascade_dispatch_order(token, reason="5_minute_timeout", db_path=db_path)
        results.append(res)
    return results


def complete_dispatch_order(
    tracking_id: str,
    actual_duration_min: Optional[float] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Marks delivery completed, logs raw performance, updates courier on-time metrics & score."""
    init_db(db_path)
    order = get_dispatch_order_by_tracking_id(tracking_id, db_path=db_path)
    if not order:
        return {"success": False, "error": f"Dispatch order '{tracking_id}' not found."}

    now = datetime.now()
    now_iso = now.isoformat()

    # Calculate actual duration
    if actual_duration_min is None:
        try:
            start_ts = datetime.fromisoformat(order["activated_at"] or order["created_at"])
            actual_duration_min = max(1.0, round((now - start_ts).total_seconds() / 60.0, 1))
        except Exception:
            actual_duration_min = float(order.get("predicted_eta_min", 25.0))

    predicted_eta = float(order.get("predicted_eta_min", 25.0))
    # Rider is on-time if actual duration <= predicted ETA + 2.0 min buffer
    was_on_time = 1 if actual_duration_min <= (predicted_eta + 2.0) else 0

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dispatch_orders SET
                    dispatch_status = 'Delivered',
                    completed_at = ?,
                    actual_duration_min = ?,
                    was_on_time = ?,
                    updated_at = ?
                WHERE tracking_id = ?;
            """, (now_iso, actual_duration_min, was_on_time, now_iso, tracking_id))

            # Update Rider performance score and rating
            rider_id = order.get("assigned_rider_id")
            rider_update = None
            if rider_id:
                cursor.execute("SELECT * FROM riders WHERE id = ?;", (rider_id,))
                r_row = cursor.fetchone()
                if r_row:
                    tot_del = int(r_row["total_deliveries"] or 0) + 1
                    ont_del = int(r_row["on_time_deliveries"] or 0) + was_on_time
                    new_score = round((ont_del / tot_del) * 100.0, 1) if tot_del > 0 else 100.0
                    curr_rating = float(r_row["rating"] or 4.8)
                    new_rating = min(5.0, round(curr_rating + (0.05 if was_on_time else -0.05), 1))

                    cursor.execute("""
                        UPDATE riders SET
                            status = 'Available',
                            total_deliveries = ?,
                            on_time_deliveries = ?,
                            performance_score = ?,
                            rating = ?,
                            last_active_at = ?,
                            updated_at = ?
                        WHERE id = ?;
                    """, (tot_del, ont_del, new_score, new_rating, now_iso, now_iso, rider_id))
                    rider_update = {
                        "id": rider_id,
                        "name": r_row["rider_name"],
                        "total_deliveries": tot_del,
                        "on_time_deliveries": ont_del,
                        "performance_score": new_score,
                        "rating": new_rating,
                    }

    finally:
        conn.close()

    # Automatically log to predictions_history for ML retraining pipeline
    log_prediction(
        order_dict={
            "Distance_km": order.get("distance_km"),
            "Weather": order.get("weather"),
            "Traffic_Level": order.get("traffic_level"),
            "Time_of_Day": order.get("time_of_day"),
            "Vehicle_Type": order.get("vehicle_type"),
            "Preparation_Time_min": order.get("prep_time_min"),
            "Courier_Experience_yrs": order.get("courier_exp_yrs"),
            "Destination_Address": order.get("client_address"),
            "Dropoff_Lat": order.get("dest_lat"),
            "Dropoff_Lng": order.get("dest_lng"),
        },
        predicted_time=predicted_eta,
        risk_status="Fast / Low Risk" if was_on_time else "High Delay Risk",
        source_type="dispatch_delivery",
        order_reference=tracking_id,
        destination_address=order.get("client_address"),
        dropoff_lat=order.get("dest_lat"),
        dropoff_lng=order.get("dest_lng"),
        hotel_id=order.get("hotel_id", 1),
        db_path=db_path
    )

    # Log audit event
    log_dispatch_event(
        dispatch_order_id=order["id"],
        tracking_id=tracking_id,
        rider_id=rider_id,
        event_type="ORDER_COMPLETED",
        details={
            "actual_duration_min": actual_duration_min,
            "predicted_eta_min": predicted_eta,
            "was_on_time": bool(was_on_time),
        },
        db_path=db_path
    )

    updated_order = get_dispatch_order_by_tracking_id(tracking_id, db_path=db_path)
    return {
        "success": True,
        "order": updated_order,
        "was_on_time": bool(was_on_time),
        "actual_duration_min": actual_duration_min,
        "predicted_eta_min": predicted_eta,
        "rider_performance": rider_update,
    }



def get_active_dispatches(
    hotel_id: Optional[int] = None,
    limit: int = 50,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves list of recent and active dispatch orders for a hotel."""
    init_db(db_path)
    if hotel_id is None:
        latest = get_hotel_profile(db_path=db_path)
        hotel_id = int(latest["id"]) if latest and latest.get("id") else 1

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM dispatch_orders
            WHERE hotel_id = ?
            ORDER BY id DESC
            LIMIT ?;
        """, (hotel_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_raw_ml_dispatch_data(
    hotel_id: Optional[int] = None,
    limit: int = 500,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves raw dispatch records for Machine Learning feature engineering and retraining."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if hotel_id is not None:
            cursor.execute("""
                SELECT 
                    id, tracking_id, distance_km, weather, traffic_level, time_of_day,
                    vehicle_type, prep_time_min, courier_exp_yrs, predicted_eta_min,
                    actual_duration_min, was_on_time,
                    was_on_time AS on_time,
                    actual_duration_min AS actual_delivery_minutes,
                    predicted_eta_min AS predicted_eta_minutes,
                    prep_time_min AS preparation_time_min,
                    courier_exp_yrs AS courier_experience_yrs,
                    dispatch_status, raw_payload_json, created_at, created_at AS timestamp
                FROM dispatch_orders
                WHERE hotel_id = ? AND dispatch_status = 'Delivered'
                ORDER BY id DESC LIMIT ?;
            """, (hotel_id, limit))
        else:
            cursor.execute("""
                SELECT 
                    id, tracking_id, distance_km, weather, traffic_level, time_of_day,
                    vehicle_type, prep_time_min, courier_exp_yrs, predicted_eta_min,
                    actual_duration_min, was_on_time,
                    was_on_time AS on_time,
                    actual_duration_min AS actual_delivery_minutes,
                    predicted_eta_min AS predicted_eta_minutes,
                    prep_time_min AS preparation_time_min,
                    courier_exp_yrs AS courier_experience_yrs,
                    dispatch_status, raw_payload_json, created_at, created_at AS timestamp
                FROM dispatch_orders
                WHERE dispatch_status = 'Delivered'
                ORDER BY id DESC LIMIT ?;
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# Re-export kitchen module API
from src.kitchen import (
    init_kitchen_tables,
    add_kitchen_order_items,
    get_kitchen_queue,
    update_kitchen_item_status,
    update_kitchen_order_status,
    generate_delivery_ticket,
    generate_kot_ticket,
    generate_dual_tickets,
    kitchen_manager,
)

