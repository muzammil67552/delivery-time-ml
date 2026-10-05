"""Automated Dispatch Engine, Proximity Rider Assignment, and Email Cascading Pipeline.

Implements:
1. Real-time proximity check: finds the closest available courier based on native GPS and performance score.
2. Automated Data Enrichment:
   - Distance: Hotel to client coordinates using Haversine / urban routing.
   - Weather Status: Live weather API lookup (Open-Meteo) with graceful fallback.
   - Time of Day: Automated window calculation (Morning, Afternoon, Evening, Night).
   - Unique Tracking ID: Automated collision-free reference generation.
3. Interactive Email Notification with [Activate Order] and [Deactivate Order] action links.
4. Cascading Fallback Engine:
   - If rider clicks 'Activate Order' -> order is accepted and assigned, courier status moves to 'On Delivery'.
   - If rider clicks 'Deactivate Order' -> courier is dropped, system cascades to next closest available courier.
   - 5-Minute Timeout: If no response within 5 minutes, token expires and order auto-cascades to next courier.
5. Performance & Raw Data Logging for ML Pipeline:
   - On-time delivery tracking boosts courier performance score & future assignment priority.
   - Raw interaction data stored permanently in SQLite for ML cleaning & model retraining.
"""

import os
import json
import logging
import secrets
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Tuple

from src.database import (
    find_closest_available_rider,
    create_dispatch_order,
    get_dispatch_order_by_tracking_id,
    get_dispatch_order_by_token,
    activate_dispatch_order,
    deactivate_and_cascade_dispatch_order,
    check_and_expire_timeout_dispatches,
    complete_dispatch_order,
    log_dispatch_email,
    get_email_logs_for_order,
    get_hotel_profile,
    get_all_riders,
    haversine_km,
)
from src.routing import estimate_road_distance_km
from src.predict import predict_delivery_time

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Automated Tracking ID Generator
# ==============================================================================

def generate_tracking_id(db_path: Optional[str] = None) -> str:
    """Generates an alphanumeric tracking ID (e.g. TRK-849201) guaranteed unique."""
    for _ in range(10):
        # 6-character random hex or uppercase digits
        code = secrets.token_hex(3).upper()
        tracking_id = f"TRK-{code}"
        existing = get_dispatch_order_by_tracking_id(tracking_id, db_path=db_path)
        if not existing:
            return tracking_id
    # Fallback with timestamp
    return f"TRK-{int(datetime.now().timestamp()) % 1000000:06d}"


# ==============================================================================
# 2. Automated Backend Data Enrichment (Weather, Time of Day, Distance)
# ==============================================================================

def compute_time_of_day(target_time: Optional[datetime] = None) -> str:
    """Calculates time of day classification based on current hour."""
    dt = target_time or datetime.now()
    hour = dt.hour
    if 5 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 22:
        return "Evening"
    else:
        return "Night"


def fetch_live_weather(lat: float, lng: float, timeout_sec: float = 2.5) -> str:
    """Queries live atmospheric weather from free Open-Meteo API.
    
    Maps WMO weather codes to the ML model's supported classes:
    ['Clear', 'Rainy', 'Foggy', 'Snowy', 'Windy'].
    Falls back gracefully to 'Clear' if network is unavailable.
    """
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat:.4f}&longitude={lng:.4f}&current_weather=true"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DeliveryML-Platform/1.0 (Merchant Dispatch Engine)"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                current = payload.get("current_weather", {})
                w_code = current.get("weathercode", 0)
                windspeed = current.get("windspeed", 0.0)

                # High wind conditions
                if windspeed >= 28.0:
                    return "Windy"

                # WMO weather code mapping:
                # 0: Clear sky, 1-3: Mainly clear, partly cloudy
                if w_code in (0, 1, 2, 3):
                    return "Clear"
                # 45, 48: Fog and depositing rime fog
                elif w_code in (45, 48):
                    return "Foggy"
                # 51-67, 80-82, 95-99: Drizzle, rain, rain showers, thunderstorm
                elif w_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
                    return "Rainy"
                # 71-77, 85-86: Snow fall, snow grains, snow showers
                elif w_code in (71, 73, 75, 77, 85, 86):
                    return "Snowy"
                else:
                    return "Clear"
    except Exception as exc:
        logger.info(f"Live Weather API lookup skipped/fallback ({exc}). Using 'Clear'.")

    return "Clear"


def compute_delivery_distance(
    hotel_lat: float,
    hotel_lng: float,
    dest_lat: Optional[float],
    dest_lng: Optional[float],
    fallback_km: float = 5.2
) -> float:
    """Computes realistic road delivery distance between hotel origin and client drop-off."""
    if dest_lat is not None and dest_lng is not None and (dest_lat != 0.0 or dest_lng != 0.0):
        # Calculate road distance using urban detour factor
        dist = estimate_road_distance_km(hotel_lat, hotel_lng, dest_lat, dest_lng)
        return max(0.5, round(dist, 1))
    return max(0.5, round(fallback_km, 1))


# ==============================================================================
# 3. Interactive Email Notification Template & SMTP Sender
# ==============================================================================

def build_interactive_email_html(
    rider_name: str,
    hotel_name: str,
    hotel_address: str,
    tracking_id: str,
    client_name: str,
    client_address: str,
    client_phone: str,
    distance_km: float,
    predicted_eta_min: float,
    activate_url: str,
    deactivate_url: str,
    expires_at_iso: str
) -> str:
    """Builds a responsive HTML email with [Activate Order] and [Deactivate Order] action buttons."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>New Urgent Delivery Dispatch • {tracking_id}</title>
  <style>
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f1f5f9;
      color: #0f172a;
    }}
    .email-wrapper {{
      max-width: 600px;
      margin: 20px auto;
      background: #ffffff;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
      border: 1px solid #e2e8f0;
    }}
    .email-header {{
      background: linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4f46e5 100%);
      padding: 24px 30px;
      color: #ffffff;
      text-align: center;
    }}
    .header-badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      background: rgba(255, 255, 255, 0.18);
      padding: 4px 10px;
      border-radius: 9999px;
      margin-bottom: 8px;
    }}
    .email-header h1 {{
      margin: 0 0 4px 0;
      font-size: 22px;
      font-weight: 800;
    }}
    .tracking-chip {{
      display: inline-block;
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.3);
      padding: 3px 10px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 13px;
      font-weight: 700;
    }}
    .email-body {{
      padding: 28px 30px;
    }}
    .greeting {{
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 12px;
    }}
    .intro-text {{
      font-size: 14px;
      color: #475569;
      line-height: 1.5;
      margin-bottom: 20px;
    }}
    .details-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    .detail-row {{
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px dashed #e2e8f0;
      font-size: 14px;
    }}
    .detail-row:last-child {{
      border-bottom: none;
    }}
    .detail-lbl {{
      color: #64748b;
      font-weight: 500;
    }}
    .detail-val {{
      color: #0f172a;
      font-weight: 700;
      text-align: right;
    }}
    .highlight-eta {{
      color: #4f46e5;
      font-size: 16px;
    }}
    .timeout-warning {{
      background: #fffbeb;
      border: 1px solid #fde68a;
      color: #92400e;
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      text-align: center;
      margin-bottom: 24px;
    }}
    .actions-container {{
      display: flex;
      gap: 14px;
      margin-bottom: 24px;
    }}
    .btn {{
      flex: 1;
      display: block;
      text-align: center;
      padding: 14px 20px;
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      border-radius: 10px;
      transition: all 0.2s ease;
      box-sizing: border-box;
    }}
    .btn-activate {{
      background: #059669;
      color: #ffffff !important;
      box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3);
    }}
    .btn-deactivate {{
      background: #ffffff;
      color: #dc2626 !important;
      border: 1.5px solid #fca5a5;
    }}
    .email-footer {{
      border-top: 1px solid #f1f5f9;
      padding-top: 16px;
      text-align: center;
      font-size: 12px;
      color: #94a3b8;
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      <div class="header-badge">&#128757; Live Dispatch Engine</div>
      <h1>Urgent Delivery Mission</h1>
      <span class="tracking-chip">&#128269; {tracking_id}</span>
    </div>

    <div class="email-body">
      <div class="greeting">Hello {rider_name},</div>
      <p class="intro-text">
        You are the <strong>closest available courier</strong> stationed near <strong>{hotel_name}</strong>.
        Please confirm this delivery order immediately by choosing one of the options below.
      </p>

      <div class="details-box">
        <div class="detail-row">
          <span class="detail-lbl">&#127976; Pickup Hub:</span>
          <span class="detail-val">{hotel_name}</span>
        </div>
        <div class="detail-row">
          <span class="detail-lbl">&#128205; Station Address:</span>
          <span class="detail-val">{hotel_address or "Dispatch Hub"}</span>
        </div>
        <div class="detail-row">
          <span class="detail-lbl">&#127937; Delivery Zone:</span>
          <span class="detail-val">{client_address}</span>
        </div>
        <div class="detail-row">
          <span class="detail-lbl">&#128755; Route Distance:</span>
          <span class="detail-val">{distance_km} km</span>
        </div>
        <div class="detail-row">
          <span class="detail-lbl">&#9201; Estimated Duration (ML):</span>
          <span class="detail-val highlight-eta">~{predicted_eta_min} minutes</span>
        </div>
      </div>

      <div class="timeout-warning">
        &#9888; <strong>Action Required within 5 Minutes:</strong><br />
        If no response is received, this mission will automatically cascade to the next nearest courier.
      </div>

      <!-- Action Buttons -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
        <tr>
          <td width="48%" align="center" style="padding-right: 8px;">
            <a href="{activate_url}" target="_blank" style="display: block; background: #059669; color: #ffffff; text-decoration: none; padding: 14px 16px; font-weight: 700; font-size: 15px; border-radius: 8px; text-align: center;">
              &#10004; Activate Order
            </a>
          </td>
          <td width="48%" align="center" style="padding-left: 8px;">
            <a href="{deactivate_url}" target="_blank" style="display: block; background: #ffffff; color: #dc2626; border: 1.5px solid #fca5a5; text-decoration: none; padding: 13px 16px; font-weight: 700; font-size: 15px; border-radius: 8px; text-align: center;">
              &#10006; Deactivate Order
            </a>
          </td>
        </tr>
      </table>

      <div class="email-footer">
        <p>Delivery Time ML Dispatch Engine &bull; Automated Mission Notification</p>
        <p>Invitation expires at: {expires_at_iso}</p>
      </div>
    </div>
  </div>
</body>
</html>"""


def send_dispatch_email(
    rider_email: str,
    rider_name: str,
    hotel_name: str,
    hotel_address: str,
    tracking_id: str,
    client_name: str,
    client_address: str,
    client_phone: str,
    distance_km: float,
    predicted_eta_min: float,
    dispatch_token: str,
    base_url: str = "http://127.0.0.1:8000",
    rider_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Generates the interactive email template and sends it to the courier.
    
    If SMTP credentials are configured in .env, transmits real SMTP email;
    otherwise logs the email as SIMULATED so it can be previewed/tested in the UI.
    """
    activate_url = f"{base_url}/api/dispatch/respond?token={dispatch_token}&action=activate"
    deactivate_url = f"{base_url}/api/dispatch/respond?token={dispatch_token}&action=deactivate"
    expires_at_iso = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

    subject = f"📦 URGENT Delivery Mission: {tracking_id} [{distance_km} km • ~{predicted_eta_min} min]"
    html_content = build_interactive_email_html(
        rider_name=rider_name,
        hotel_name=hotel_name,
        hotel_address=hotel_address,
        tracking_id=tracking_id,
        client_name=client_name,
        client_address=client_address,
        client_phone=client_phone,
        distance_km=distance_km,
        predicted_eta_min=predicted_eta_min,
        activate_url=activate_url,
        deactivate_url=deactivate_url,
        expires_at_iso=expires_at_iso
    )

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", f"dispatch@{urllib.parse.urlparse(base_url).hostname or 'deliveryml.local'}")

    status_str = "SIMULATED"
    error_msg = None

    if smtp_host and smtp_user and smtp_password and rider_email:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = rider_email
            part_html = MIMEText(html_content, "html")
            msg.attach(part_html)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=5.0) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [rider_email], msg.as_string())
            status_str = "SENT"
        except Exception as exc:
            status_str = "FAILED"
            error_msg = str(exc)
            logger.warning(f"SMTP send failed: {exc}. Saved to email audit log as FAILED.")

    # Record email into SQLite audit log
    log_id = log_dispatch_email(
        tracking_id=tracking_id,
        rider_id=rider_id,
        recipient_email=rider_email or "courier@deliveryml.local",
        subject=subject,
        html_body=html_content,
        status=status_str,
        action_token=dispatch_token,
        db_path=db_path
    )

    return {
        "success": status_str in ("SENT", "SIMULATED"),
        "status": status_str,
        "email_log_id": log_id,
        "recipient": rider_email,
        "subject": subject,
        "activate_url": activate_url,
        "deactivate_url": deactivate_url,
        "expires_at": expires_at_iso,
        "html_preview": html_content,
        "error": error_msg,
    }


# ==============================================================================
# 4. Master Automated Dispatch Pipeline Executor
# ==============================================================================

def execute_automated_dispatch(
    client_name: str,
    client_phone: str,
    client_address: str,
    hotel_id: int = 1,
    tracking_id: Optional[str] = None,
    dest_lat: Optional[float] = None,
    dest_lng: Optional[float] = None,
    vehicle_type: Optional[str] = None,
    prep_time_min: Optional[float] = None,
    traffic_level: Optional[str] = None,
    base_url: str = "http://127.0.0.1:8000",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Coordinates the entire automated dispatch workflow:
    
    1. Generates unique tracking ID.
    2. Auto-enriches with distance, live weather API status, and time of day.
    3. Infers duration with ML production model.
    4. Scans and selects closest available courier.
    5. Dispatches interactive email notification with 5-minute timer.
    6. Persists raw payload for Machine Learning retraining.
    """
    hotel_profile = get_hotel_profile(hotel_id=hotel_id, db_path=db_path) or {}
    hotel_name = hotel_profile.get("hotel_name") or "Express Hub"
    hotel_address = hotel_profile.get("branch_or_address") or "Dispatch Origin"
    hotel_lat = float(hotel_profile.get("latitude") or 40.7306)
    hotel_lng = float(hotel_profile.get("longitude") or -73.9866)

    # 1. Automated Tracking ID
    order_tracking_id = tracking_id.strip() if tracking_id and tracking_id.strip() else generate_tracking_id(db_path=db_path)

    # 2. Automated Enrichment: Coordinates & Distance
    if (dest_lat is None or dest_lng is None or (dest_lat == 0.0 and dest_lng == 0.0)):
        # Synthesize realistic client offset coordinates near hotel if coordinates weren't directly picked on map
        dest_lat = round(hotel_lat + 0.015, 6)
        dest_lng = round(hotel_lng + 0.012, 6)

    distance_km = compute_delivery_distance(hotel_lat, hotel_lng, dest_lat, dest_lng)

    # 2b. Automated Enrichment: Live Weather Status
    live_weather = fetch_live_weather(hotel_lat, hotel_lng)

    # 2c. Automated Enrichment: Time of Day
    time_of_day = compute_time_of_day()

    # Defaults from hotel profile
    prep_time = float(prep_time_min if prep_time_min is not None else (hotel_profile.get("default_prep_time_min") or 15.0))
    vehicle = str(vehicle_type or hotel_profile.get("default_vehicle_type") or "Scooter")
    traffic = str(traffic_level or "Medium")

    # 3. Find Closest Available Courier
    closest_rider = find_closest_available_rider(
        hotel_id=hotel_id,
        hotel_lat=hotel_lat,
        hotel_lng=hotel_lng,
        db_path=db_path
    )

    rider_exp = float(closest_rider.get("courier_exp_yrs") or 2.5) if closest_rider else 2.5
    if closest_rider and closest_rider.get("vehicle_type"):
        vehicle = closest_rider.get("vehicle_type")

    # 4. Predict Delivery ETA using Machine Learning Pipeline
    raw_input_dict = {
        "Distance_km": distance_km,
        "Weather": live_weather,
        "Traffic_Level": traffic,
        "Time_of_Day": time_of_day,
        "Vehicle_Type": vehicle,
        "Preparation_Time_min": prep_time,
        "Courier_Experience_yrs": rider_exp,
    }
    try:
        predicted_eta = float(predict_delivery_time(raw_input_dict))
    except Exception as pred_err:
        logger.warning(f"Prediction failed ({pred_err}), using default ETA.")
        predicted_eta = round(15.0 + distance_km * 2.5, 1)


    # 5. Generate Dispatch Security Token (for email button links)
    dispatch_token = secrets.token_urlsafe(16)
    token_expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()

    # 6. Save Dispatch Order into SQLite
    assigned_id = closest_rider.get("id") if closest_rider else None
    assigned_name = closest_rider.get("rider_name") if closest_rider else None
    assigned_email = closest_rider.get("email") if closest_rider else None

    raw_payload_dict = {
        "tracking_id": order_tracking_id,
        "client_name": client_name,
        "client_phone": client_phone,
        "client_address": client_address,
        "hotel_name": hotel_name,
        "hotel_address": hotel_address,
        "hotel_lat": hotel_lat,
        "hotel_lng": hotel_lng,
        "dest_lat": dest_lat,
        "dest_lng": dest_lng,
        "distance_km": distance_km,
        "weather": live_weather,
        "traffic_level": traffic,
        "time_of_day": time_of_day,
        "vehicle_type": vehicle,
        "prep_time_min": prep_time,
        "courier_exp_yrs": rider_exp,
        "predicted_eta_min": predicted_eta,
        "assigned_rider": closest_rider,
    }

    order_record = create_dispatch_order({
        "hotel_id": hotel_id,
        "tracking_id": order_tracking_id,
        "client_name": client_name,
        "client_phone": client_phone,
        "client_address": client_address,
        "dest_lat": dest_lat,
        "dest_lng": dest_lng,
        "distance_km": distance_km,
        "weather": live_weather,
        "traffic_level": traffic,
        "time_of_day": time_of_day,
        "vehicle_type": vehicle,
        "prep_time_min": prep_time,
        "courier_exp_yrs": rider_exp,
        "predicted_eta_min": predicted_eta,
        "assigned_rider_id": assigned_id,
        "rider_name": assigned_name,
        "rider_email": assigned_email,
        "dispatch_status": "Pending_Rider" if closest_rider else "Unassigned_No_Riders",
        "dispatch_attempts": 1,
        "dispatch_token": dispatch_token,
        "token_expires_at": token_expires_at,
        "raw_payload_json": json.dumps(raw_payload_dict),
    }, db_path=db_path)

    # 7. Dispatch Interactive Email to Rider (if courier found)
    email_result = None
    if closest_rider:
        email_result = send_dispatch_email(
            rider_email=closest_rider.get("email") or f"{closest_rider['rider_name'].lower().replace(' ', '.')}@example.com",
            rider_name=closest_rider["rider_name"],
            hotel_name=hotel_name,
            hotel_address=hotel_address,
            tracking_id=order_tracking_id,
            client_name=client_name,
            client_address=client_address,
            client_phone=client_phone,
            distance_km=distance_km,
            predicted_eta_min=predicted_eta,
            dispatch_token=dispatch_token,
            base_url=base_url,
            rider_id=closest_rider["id"],
            db_path=db_path
        )

    return {
        "success": True,
        "tracking_id": order_tracking_id,
        "dispatch_status": order_record.get("dispatch_status"),
        "distance_km": distance_km,
        "weather": live_weather,
        "traffic_level": traffic,
        "time_of_day": time_of_day,
        "predicted_eta_min": predicted_eta,
        "assigned_rider": closest_rider,
        "dispatch_token": dispatch_token,
        "token_expires_at": token_expires_at,
        "email_dispatch": email_result,
        "order": order_record,
    }


def handle_cascading_dispatch(
    token: str,
    reason: str = "rider_declined",
    base_url: str = "http://127.0.0.1:8000",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Cascades order to the next closest available courier and repeats the email notification."""
    cascade_res = deactivate_and_cascade_dispatch_order(token, reason=reason, db_path=db_path)
    if cascade_res.get("success") and cascade_res.get("cascaded") and cascade_res.get("next_rider"):
        next_rider = cascade_res["next_rider"]
        order = cascade_res.get("order") or {}
        hotel_profile = get_hotel_profile(hotel_id=order.get("hotel_id", 1), db_path=db_path) or {}

        email_res = send_dispatch_email(
            rider_email=next_rider.get("email") or f"{next_rider['rider_name'].lower().replace(' ', '.')}@example.com",
            rider_name=next_rider["rider_name"],
            hotel_name=hotel_profile.get("hotel_name") or "Express Hub",
            hotel_address=hotel_profile.get("branch_or_address") or "Dispatch Origin",
            tracking_id=order.get("tracking_id", ""),
            client_name=order.get("client_name", "Valued Customer"),
            client_address=order.get("client_address", ""),
            client_phone=order.get("client_phone", ""),
            distance_km=float(order.get("distance_km", 5.0)),
            predicted_eta_min=float(order.get("predicted_eta_min", 25.0)),
            dispatch_token=order.get("dispatch_token", ""),
            base_url=base_url,
            rider_id=next_rider["id"],
            db_path=db_path
        )
        cascade_res["email_dispatch"] = email_res
    return cascade_res


def process_timeout_cascades(base_url: str = "http://127.0.0.1:8000", db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Finds orders expired beyond 5 minutes and auto-cascades them with fresh email dispatches."""
    from src.database import get_db_connection
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
        res = handle_cascading_dispatch(token, reason="5_minute_timeout", base_url=base_url, db_path=db_path)
        results.append(res)
    return results

