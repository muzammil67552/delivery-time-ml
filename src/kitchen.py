"""Kitchen Management Module, Thermal Ticket Generator (ESC/POS), and Real-Time WebSocket.

Features:
1. Kitchen Database Schema (SQLite `kitchen_queue` table)
   - Linked to main orders (order_id, tracking_id)
   - Fields: order_id, tracking_id, item_name, quantity, special_instructions, status, timestamp
2. Dual Thermal Ticket Layout Generator (ESC/POS Plain Text)
   - Delivery Ticket: Tracking ID, Client Name, Contact, Address, Full Item List, Total Bill, Time
   - Kitchen Order Ticket (KOT): Tracking ID, Item Names, Quantities, Special Instructions (EXCLUDES ALL PRICING)
   - Supports 58mm (32 chars) and 80mm (42-48 chars)
3. Real-Time Kitchen WebSocket Connection Manager (/ws/kitchen)
   - Broadcasts newly confirmed order items and special instructions instantly without page refresh
"""

import asyncio
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set
from fastapi import WebSocket


# ==============================================================================
# 1. Database Schema & SQLite Data Access
# ==============================================================================

VALID_KITCHEN_STATUSES = {"Pending", "Preparing", "Ready", "Completed"}


def init_kitchen_tables(conn: sqlite3.Connection) -> None:
    """Initializes the kitchen_queue SQLite table and corresponding performance indices."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kitchen_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER DEFAULT 1,
                order_id TEXT NOT NULL,
                tracking_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                special_instructions TEXT,
                status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Preparing', 'Ready', 'Completed')),
                unit_price REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kitchen_tracking 
            ON kitchen_queue(tracking_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kitchen_order 
            ON kitchen_queue(order_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kitchen_status 
            ON kitchen_queue(status);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kitchen_hotel 
            ON kitchen_queue(hotel_id);
        """)


def add_kitchen_order_items(
    order_id: str,
    tracking_id: str,
    items: List[Dict[str, Any]],
    hotel_id: int = 1,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Inserts a batch of food/beverage items into the kitchen queue linked to the order."""
    from src.database import get_db_connection

    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True

    now_iso = datetime.now().isoformat()
    inserted_records: List[Dict[str, Any]] = []

    try:
        with active_conn:
            cursor = active_conn.cursor()
            for it in items:
                name = str(it.get("item_name") or it.get("name") or "Express Chef Special").strip()
                qty = max(1, int(it.get("quantity") or it.get("qty") or 1))
                instr = it.get("special_instructions")
                if instr is not None:
                    instr = str(instr).strip()
                    if not instr:
                        instr = None
                status = str(it.get("status") or "Pending").capitalize().strip()
                if status not in VALID_KITCHEN_STATUSES:
                    status = "Pending"
                price = float(it.get("unit_price") or it.get("price") or 0.0)

                cursor.execute("""
                    INSERT INTO kitchen_queue (
                        hotel_id, order_id, tracking_id, item_name, quantity,
                        special_instructions, status, unit_price, timestamp,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    hotel_id,
                    str(order_id).strip(),
                    str(tracking_id).strip(),
                    name,
                    qty,
                    instr,
                    status,
                    price,
                    now_iso,
                    now_iso,
                    now_iso,
                ))
                new_id = cursor.lastrowid
                inserted_records.append({
                    "id": new_id,
                    "hotel_id": hotel_id,
                    "order_id": order_id,
                    "tracking_id": tracking_id,
                    "item_name": name,
                    "quantity": qty,
                    "special_instructions": instr,
                    "status": status,
                    "unit_price": price,
                    "timestamp": now_iso,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                })
        return inserted_records
    finally:
        if should_close:
            active_conn.close()


def get_kitchen_queue(
    hotel_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    tracking_id: Optional[str] = None,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves kitchen items grouped by order or chronologically for kitchen display."""
    from src.database import get_db_connection

    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True

    try:
        cursor = active_conn.cursor()
        query = "SELECT * FROM kitchen_queue WHERE 1=1"
        params: List[Any] = []

        if hotel_id is not None:
            query += " AND hotel_id = ?"
            params.append(hotel_id)

        if tracking_id:
            query += " AND tracking_id = ?"
            params.append(tracking_id.strip())

        if status_filter:
            statuses = [s.strip().capitalize() for s in status_filter.split(",") if s.strip()]
            if statuses:
                placeholders = ",".join("?" for _ in statuses)
                query += f" AND status IN ({placeholders})"
                params.extend(statuses)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if should_close:
            active_conn.close()


def update_kitchen_item_status(
    item_id: int,
    new_status: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Updates the status of a specific food/beverage item in the kitchen queue."""
    from src.database import get_db_connection

    clean_status = str(new_status).capitalize().strip()
    if clean_status not in VALID_KITCHEN_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_KITCHEN_STATUSES}")

    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True

    now_iso = datetime.now().isoformat()
    try:
        with active_conn:
            cursor = active_conn.cursor()
            cursor.execute("""
                UPDATE kitchen_queue 
                SET status = ?, updated_at = ? 
                WHERE id = ?;
            """, (clean_status, now_iso, item_id))
            cursor.execute("SELECT * FROM kitchen_queue WHERE id = ?;", (item_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        if should_close:
            active_conn.close()


def update_kitchen_order_status(
    tracking_id: str,
    new_status: str,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Updates all items of a tracking_id to a new status simultaneously (e.g. all Ready)."""
    from src.database import get_db_connection

    clean_status = str(new_status).capitalize().strip()
    if clean_status not in VALID_KITCHEN_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {VALID_KITCHEN_STATUSES}")

    should_close = False
    active_conn = conn
    if active_conn is None:
        active_conn = get_db_connection(db_path)
        should_close = True

    now_iso = datetime.now().isoformat()
    try:
        with active_conn:
            cursor = active_conn.cursor()
            cursor.execute("""
                UPDATE kitchen_queue 
                SET status = ?, updated_at = ? 
                WHERE tracking_id = ?;
            """, (clean_status, now_iso, tracking_id.strip()))
            cursor.execute("SELECT * FROM kitchen_queue WHERE tracking_id = ?;", (tracking_id.strip(),))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        if should_close:
            active_conn.close()


# ==============================================================================
# 2. Dual Thermal Ticket Layout Generator (ESC/POS Plain Text)
# ==============================================================================

def _get_column_width(paper_width: str) -> int:
    """Returns character width for standard thermal printer sizes."""
    cleaned = str(paper_width).lower().replace(" ", "")
    if "58" in cleaned:
        return 32  # 58mm standard width: 32 columns (Font A)
    return 42      # 80mm standard safe width: 42 columns (Font A)


def _wrap_lines(text: str, width: int, indent: str = "") -> List[str]:
    """Wraps text cleanly within the character column limit."""
    words = str(text or "").strip().split()
    if not words:
        return []
    lines: List[str] = []
    current_line = indent
    available_width = width - len(indent)

    for word in words:
        if len(current_line.strip()) == 0:
            current_line += word
        elif len(current_line) + 1 + len(word) <= width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = indent + word
    if current_line.strip():
        lines.append(current_line)
    return lines


def generate_delivery_ticket(order_data: Dict[str, Any], paper_width: str = "80mm") -> str:
    """Formats raw order data into a clean ESC/POS text layout for Customer Delivery Tickets.
    
    Contains:
    - Tracking ID
    - Client Name
    - Contact Phone
    - Delivery Address
    - Full Item List with Unit Price and Subtotal
    - Total Bill (Subtotal, Delivery Fee, Tax, Total)
    - Date & Time
    """
    w = _get_column_width(paper_width)
    border_heavy = "=" * w
    border_light = "-" * w

    hotel_name = str(order_data.get("hotel_name") or "DELIVERY ML PLATFORM").upper()
    tracking_id = str(order_data.get("tracking_id") or "TRK-000000").strip()
    order_id = str(order_data.get("order_id") or order_data.get("order_reference") or tracking_id).strip()
    client_name = str(order_data.get("client_name") or "Valued Customer").strip()
    client_phone = str(order_data.get("client_phone") or "N/A").strip()
    client_address = str(order_data.get("client_address") or "Customer Address").strip()
    
    timestamp = order_data.get("timestamp") or order_data.get("created_at")
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        try:
            dt = datetime.fromisoformat(str(timestamp))
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            timestamp = str(timestamp)[:19].replace("T", " ")

    items: List[Dict[str, Any]] = order_data.get("items") or []
    if not items and order_data.get("item_name"):
        items = [{
            "item_name": order_data.get("item_name"),
            "quantity": order_data.get("quantity", 1),
            "unit_price": order_data.get("unit_price", 0.0),
            "special_instructions": order_data.get("special_instructions"),
        }]
    if not items:
        # Fallback default item representation
        items = [{
            "item_name": "Express Kitchen Gourmet Combo",
            "quantity": 1,
            "unit_price": 18.50,
            "special_instructions": None,
        }]

    lines: List[str] = [
        border_heavy,
        hotel_name.center(w),
        "DELIVERY RECEIPT & DISPATCH TICKET".center(w),
        border_heavy,
        f"TRACKING ID: {tracking_id}".ljust(w),
        f"ORDER ID:    {order_id}".ljust(w),
        f"DATE/TIME:   {timestamp}".ljust(w),
        border_light,
        "CUSTOMER DISPATCH DETAILS:".ljust(w),
        f"Name:    {client_name}".ljust(w),
        f"Phone:   {client_phone}".ljust(w),
        "Address:".ljust(w),
    ]

    for addr_line in _wrap_lines(client_address, w, indent="  "):
        lines.append(addr_line.ljust(w))

    lines.append(border_light)

    # Item Column Layout
    subtotal = 0.0
    if w <= 36:
        # 58mm compact layout
        lines.append("ITEM             QTY       TOTAL".ljust(w))
        lines.append(border_light)
        for it in items:
            name = str(it.get("item_name") or "Item")
            qty = max(1, int(it.get("quantity") or 1))
            price = float(it.get("unit_price") or it.get("price") or 0.0)
            if price == 0.0:
                price = 12.00  # standard fallback price if unpriced
            line_tot = qty * price
            subtotal += line_tot

            name_col = name[:16].ljust(16)
            qty_col = str(qty).rjust(3)
            tot_col = f"${line_tot:.2f}".rjust(11)
            lines.append(f"{name_col} {qty_col} {tot_col}".ljust(w))

            instr = it.get("special_instructions")
            if instr:
                for in_line in _wrap_lines(f"* {instr}", w, indent="  "):
                    lines.append(in_line.ljust(w))
    else:
        # 80mm standard layout
        lines.append("ITEM DESCRIPTION        QTY   PRICE    TOTAL".ljust(w))
        lines.append(border_light)
        for it in items:
            name = str(it.get("item_name") or "Item")
            qty = max(1, int(it.get("quantity") or 1))
            price = float(it.get("unit_price") or it.get("price") or 0.0)
            if price == 0.0:
                price = 14.50
            line_tot = qty * price
            subtotal += line_tot

            name_col = name[:22].ljust(22)
            qty_col = str(qty).rjust(3)
            price_col = f"${price:.2f}".rjust(8)
            tot_col = f"${line_tot:.2f}".rjust(8)
            lines.append(f"{name_col} {qty_col} {price_col} {tot_col}".ljust(w))

            instr = it.get("special_instructions")
            if instr:
                for in_line in _wrap_lines(f"* Note: {instr}", w, indent="  "):
                    lines.append(in_line.ljust(w))

    lines.append(border_light)

    # Billing Calculation
    delivery_fee = float(order_data.get("delivery_fee") or 3.50)
    tax_rate = float(order_data.get("tax_rate") or 0.08)
    tax_amt = round(subtotal * tax_rate, 2)
    grand_total = subtotal + delivery_fee + tax_amt

    def _fmt_bill_line(label: str, val: float) -> str:
        val_str = f"${val:.2f}"
        space = w - len(label) - len(val_str)
        return label + (" " * max(1, space)) + val_str

    lines.append(_fmt_bill_line("Subtotal:", subtotal))
    lines.append(_fmt_bill_line("Delivery Fee:", delivery_fee))
    lines.append(_fmt_bill_line("Sales Tax:", tax_amt))
    lines.append(border_light)
    lines.append(_fmt_bill_line("TOTAL BILL:", grand_total))
    lines.append(border_heavy)

    # Footer
    lines.append("Thank you for your order!".center(w))
    lines.append("Fast & Fresh Delivery Guaranteed".center(w))
    lines.append(border_heavy)
    lines.append("[CUT PAPER HERE]".center(w))
    lines.append("\n\n")

    return "\n".join(lines)


def generate_kot_ticket(order_data: Dict[str, Any], paper_width: str = "80mm") -> str:
    """Formats raw order data into a Kitchen Order Ticket (KOT) text layout for kitchen staff.
    
    Contains:
    - Tracking ID
    - Order Reference
    - Timestamp
    - Item Names & Quantities
    - Special Instructions (Customizations)
    
    CRITICAL CONSTRAINT:
    - Must exclude ALL pricing, billing, and payment information for kitchen staff!
    """
    w = _get_column_width(paper_width)
    border_heavy = "=" * w
    border_light = "-" * w

    tracking_id = str(order_data.get("tracking_id") or "TRK-000000").strip()
    order_id = str(order_data.get("order_id") or order_data.get("order_reference") or tracking_id).strip()
    hotel_name = str(order_data.get("hotel_name") or "EXPRESS KITCHEN").upper()
    
    timestamp = order_data.get("timestamp") or order_data.get("created_at")
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        try:
            dt = datetime.fromisoformat(str(timestamp))
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            timestamp = str(timestamp)[:19].replace("T", " ")

    items: List[Dict[str, Any]] = order_data.get("items") or []
    if not items and order_data.get("item_name"):
        items = [{
            "item_name": order_data.get("item_name"),
            "quantity": order_data.get("quantity", 1),
            "special_instructions": order_data.get("special_instructions"),
        }]
    if not items:
        items = [{
            "item_name": "Express Kitchen Chef Combo",
            "quantity": 1,
            "special_instructions": "Cook standard",
        }]

    lines: List[str] = [
        border_heavy,
        hotel_name.center(w),
        "*** KITCHEN ORDER TICKET (KOT) ***".center(w),
        border_heavy,
        f"TRACKING ID: {tracking_id}".ljust(w),
        f"ORDER REF:   {order_id}".ljust(w),
        f"LOGGED AT:   {timestamp}".ljust(w),
        "STATION:     HOT & COLD PREP LINE".ljust(w),
        border_light,
        "QTY   FOOD / BEVERAGE ITEM".ljust(w),
        border_light,
    ]

    total_qty = 0
    for it in items:
        name = str(it.get("item_name") or "Special Item").upper()
        qty = max(1, int(it.get("quantity") or 1))
        total_qty += qty
        instr = it.get("special_instructions")

        lines.append(f"[{qty}x]  {name}".ljust(w))
        if instr:
            # Highlight special instructions prominently for kitchen cooks
            formatted_instr = f">>> INSTRUCTION: {instr}"
            for in_line in _wrap_lines(formatted_instr, w, indent="     "):
                lines.append(in_line.ljust(w))
        lines.append("")  # spacing between items for clear reading

    lines.append(border_light)
    lines.append(f"TOTAL PREPARATION ITEMS: {total_qty}".ljust(w))
    lines.append("STATUS: PENDING KITCHEN PREPARATION".ljust(w))
    lines.append(border_heavy)
    lines.append("*** FOR KITCHEN USE ONLY - NO BILLING ***".center(w))
    lines.append(border_heavy)
    lines.append("[CUT PAPER HERE]".center(w))
    lines.append("\n\n")

    return "\n".join(lines)


def generate_dual_tickets(order_data: Dict[str, Any], paper_width: str = "80mm") -> Dict[str, str]:
    """Helper that generates both Delivery Ticket and Kitchen Order Ticket (KOT) simultaneously."""
    return {
        "delivery_ticket": generate_delivery_ticket(order_data, paper_width=paper_width),
        "kot_ticket": generate_kot_ticket(order_data, paper_width=paper_width),
        "paper_width": paper_width,
        "tracking_id": order_data.get("tracking_id", ""),
    }


# ==============================================================================
# 3. Real-Time Kitchen WebSocket Connection Manager
# ==============================================================================

class KitchenConnectionManager:
    """Manages active WebSocket connections for Kitchen Display System (KDS) terminals.
    
    Supports:
    - Broadcast of new food/beverage orders with special instructions instantly.
    - Status updates (Pending -> Preparing -> Ready) synced across all kitchen screens.
    """

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.hotel_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, hotel_id: Optional[int] = None) -> None:
        """Accepts and registers a new kitchen WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        hid = hotel_id or 1
        if hid not in self.hotel_connections:
            self.hotel_connections[hid] = set()
        self.hotel_connections[hid].add(websocket)

    def disconnect(self, websocket: WebSocket, hotel_id: Optional[int] = None) -> None:
        """Removes a disconnected kitchen WebSocket."""
        self.active_connections.discard(websocket)
        hid = hotel_id or 1
        if hid in self.hotel_connections:
            self.hotel_connections[hid].discard(websocket)

    async def broadcast_kitchen_order(
        self,
        order_payload: Dict[str, Any],
        hotel_id: Optional[int] = None,
    ) -> int:
        """Broadcasts only food/beverage items and special instructions to connected kitchen terminals.
        
        Strictly excludes customer private billing and pricing info.
        """
        # Build pure kitchen payload
        items = order_payload.get("items") or []
        kitchen_event = {
            "event": "new_kitchen_order",
            "tracking_id": order_payload.get("tracking_id"),
            "order_id": order_payload.get("order_id") or order_payload.get("tracking_id"),
            "hotel_id": hotel_id or order_payload.get("hotel_id") or 1,
            "timestamp": order_payload.get("timestamp") or datetime.now().isoformat(),
            "items": [
                {
                    "id": it.get("id"),
                    "item_name": it.get("item_name"),
                    "quantity": it.get("quantity", 1),
                    "special_instructions": it.get("special_instructions"),
                    "status": it.get("status", "Pending"),
                }
                for it in items
            ],
            "total_items": sum(it.get("quantity", 1) for it in items),
        }

        recipients = list(self.active_connections)
        delivered_count = 0
        for ws in recipients:
            try:
                await ws.send_json(kitchen_event)
                delivered_count += 1
            except Exception:
                self.disconnect(ws, hotel_id)

        return delivered_count

    async def broadcast_status_change(
        self,
        item_id: int,
        tracking_id: str,
        new_status: str,
        hotel_id: Optional[int] = None,
    ) -> int:
        """Broadcasts an item status transition (e.g. Preparing or Ready) to all kitchen displays."""
        status_event = {
            "event": "item_status_updated",
            "item_id": item_id,
            "tracking_id": tracking_id,
            "status": new_status,
            "updated_at": datetime.now().isoformat(),
        }
        recipients = list(self.active_connections)
        delivered_count = 0
        for ws in recipients:
            try:
                await ws.send_json(status_event)
                delivered_count += 1
            except Exception:
                self.disconnect(ws, hotel_id)

        return delivered_count


# Global singleton instance of KitchenConnectionManager
kitchen_manager = KitchenConnectionManager()
