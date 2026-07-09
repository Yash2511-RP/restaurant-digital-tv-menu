from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "restaurant_menu.db"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"screen-{uuid.uuid4().hex[:6]}"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def bool_row(value: object) -> int:
    return 1 if bool(value) else 0


def parse_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Body must be valid JSON") from exc


def require(payload: dict, *fields: str) -> None:
    missing = [field for field in fields if payload.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required field: {', '.join(missing)}")


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def ensure_location_columns(conn: sqlite3.Connection, location_id: str) -> None:
    for table in ("categories", "menu_items", "tv_screens"):
        if not column_exists(conn, table, "location_id"):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN location_id TEXT")
        conn.execute(f"UPDATE {table} SET location_id = ? WHERE location_id IS NULL", (location_id,))


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS locations (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              address TEXT NOT NULL DEFAULT '',
              phone TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
              id TEXT PRIMARY KEY,
              location_id TEXT REFERENCES locations(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS menu_items (
              id TEXT PRIMARY KEY,
              location_id TEXT REFERENCES locations(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
              price REAL NOT NULL,
              image_url TEXT NOT NULL DEFAULT '',
              available INTEGER NOT NULL DEFAULT 1,
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tv_screens (
              id TEXT PRIMARY KEY,
              location_id TEXT REFERENCES locations(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              slug TEXT NOT NULL UNIQUE,
              show_images INTEGER NOT NULL DEFAULT 1,
              show_sold_out INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tv_screen_categories (
              id TEXT PRIMARY KEY,
              tv_screen_id TEXT NOT NULL REFERENCES tv_screens(id) ON DELETE CASCADE,
              category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
              UNIQUE(tv_screen_id, category_id)
            );

            CREATE TABLE IF NOT EXISTS tv_screen_items (
              id TEXT PRIMARY KEY,
              tv_screen_id TEXT NOT NULL REFERENCES tv_screens(id) ON DELETE CASCADE,
              menu_item_id TEXT NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
              UNIQUE(tv_screen_id, menu_item_id)
            );

            CREATE TABLE IF NOT EXISTS display_settings (
              id TEXT PRIMARY KEY,
              tv_screen_id TEXT NOT NULL UNIQUE REFERENCES tv_screens(id) ON DELETE CASCADE,
              restaurant_name TEXT NOT NULL,
              background_color TEXT NOT NULL,
              text_color TEXT NOT NULL,
              accent_color TEXT NOT NULL,
              price_color TEXT NOT NULL,
              title_size INTEGER NOT NULL,
              item_size INTEGER NOT NULL,
              price_size INTEGER NOT NULL,
              logo_url TEXT NOT NULL DEFAULT '',
              background_image_url TEXT NOT NULL DEFAULT ''
            );
            """
        )

        created = now()
        location_count = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        if location_count:
            default_location_id = conn.execute("SELECT id FROM locations ORDER BY created_at LIMIT 1").fetchone()["id"]
        else:
            default_location_id = new_id()
            conn.execute(
                """
                INSERT INTO locations (id, name, address, phone, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (default_location_id, "Downtown Location", "100 Main Street", "(555) 010-1000", created),
            )

        ensure_location_columns(conn, default_location_id)

        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count:
            uptown_exists = conn.execute("SELECT 1 FROM tv_screens WHERE slug = ?", ("uptown-main-tv",)).fetchone()
            if not uptown_exists:
                seed_second_location(conn, created)
            return

        categories = [
            ("Breakfast", 1),
            ("Signature Plates", 2),
            ("Drinks", 3),
            ("Desserts", 4),
        ]
        category_ids: dict[str, str] = {}
        for name, sort_order in categories:
            category_id = new_id()
            category_ids[name] = category_id
            conn.execute(
                "INSERT INTO categories (id, location_id, name, sort_order, created_at) VALUES (?, ?, ?, ?, ?)",
                (category_id, default_location_id, name, sort_order, created),
            )

        items = [
            ("Sunrise Tacos", "Scrambled eggs, roasted salsa, queso fresco, cilantro.", "Breakfast", 9.50, "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Cinnamon French Toast", "Brioche, berries, maple cream, powdered sugar.", "Breakfast", 11.00, "https://images.unsplash.com/photo-1484723091739-30a097e8f929?auto=format&fit=crop&w=600&q=80", 1, 2),
            ("Smash Burger", "Double patty, cheddar, pickles, house sauce, fries.", "Signature Plates", 14.75, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Grilled Chicken Bowl", "Herbed rice, avocado, charred corn, lime crema.", "Signature Plates", 13.25, "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80", 1, 2),
            ("Spicy Rigatoni", "Tomato cream sauce, chili, parmesan, basil.", "Signature Plates", 16.50, "https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=600&q=80", 0, 3),
            ("House Lemonade", "Fresh lemon, cane sugar, mint.", "Drinks", 4.50, "https://images.unsplash.com/photo-1523371054106-bbf80586c38c?auto=format&fit=crop&w=600&q=80", 1, 1),
            ("Iced Hibiscus Tea", "Bright hibiscus, citrus, light sweetness.", "Drinks", 4.25, "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=600&q=80", 1, 2),
            ("Chocolate Lava Cake", "Warm chocolate cake, vanilla ice cream.", "Desserts", 8.75, "https://images.unsplash.com/photo-1606890737304-57a1ca8a5b62?auto=format&fit=crop&w=600&q=80", 1, 1),
        ]
        for name, description, category, price, image_url, available, sort_order in items:
            conn.execute(
                """
                INSERT INTO menu_items (
                  id, location_id, name, description, category_id, price, image_url, available,
                  sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    default_location_id,
                    name,
                    description,
                    category_ids[category],
                    price,
                    image_url,
                    available,
                    sort_order,
                    created,
                    created,
                ),
            )

        screens = [
            ("Main TV", "main-tv", ["Breakfast", "Signature Plates", "Desserts"]),
            ("Drinks TV", "drinks-tv", ["Drinks"]),
        ]
        for name, slug, category_names in screens:
            tv_id = new_id()
            conn.execute(
                """
                INSERT INTO tv_screens (id, name, slug, show_images, show_sold_out, created_at)
                VALUES (?, ?, ?, 1, 1, ?)
                """,
                (tv_id, name, slug, created),
            )
            conn.execute("UPDATE tv_screens SET location_id = ? WHERE id = ?", (default_location_id, tv_id))
            insert_default_settings(conn, tv_id)
            for category_name in category_names:
                conn.execute(
                    """
                    INSERT INTO tv_screen_categories (id, tv_screen_id, category_id)
                    VALUES (?, ?, ?)
                    """,
                    (new_id(), tv_id, category_ids[category_name]),
                )

        seed_second_location(conn, created)


def seed_second_location(conn: sqlite3.Connection, created: str) -> None:
    location_id = new_id()
    conn.execute(
        """
        INSERT INTO locations (id, name, address, phone, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (location_id, "Uptown Location", "220 Market Avenue", "(555) 010-2200", created),
    )

    category_ids: dict[str, str] = {}
    for name, sort_order in [("Lunch", 1), ("Coffee Bar", 2), ("Grab & Go", 3)]:
        category_id = new_id()
        category_ids[name] = category_id
        conn.execute(
            "INSERT INTO categories (id, location_id, name, sort_order, created_at) VALUES (?, ?, ?, ?, ?)",
            (category_id, location_id, name, sort_order, created),
        )

    items = [
        ("Turkey Club", "Roasted turkey, bacon, tomato, lettuce, garlic aioli.", "Lunch", 12.50, "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=600&q=80", 1, 1),
        ("Market Salad", "Greens, roasted vegetables, feta, lemon vinaigrette.", "Lunch", 10.75, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=600&q=80", 1, 2),
        ("Cold Brew", "Slow-steeped coffee served over ice.", "Coffee Bar", 4.75, "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=600&q=80", 1, 1),
        ("Blueberry Muffin", "Bakery muffin with lemon sugar crumble.", "Grab & Go", 3.95, "https://images.unsplash.com/photo-1607958996333-41aef7caefaa?auto=format&fit=crop&w=600&q=80", 1, 1),
    ]
    for name, description, category, price, image_url, available, sort_order in items:
        conn.execute(
            """
            INSERT INTO menu_items (
              id, location_id, name, description, category_id, price, image_url, available,
              sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(),
                location_id,
                name,
                description,
                category_ids[category],
                price,
                image_url,
                available,
                sort_order,
                created,
                created,
            ),
        )

    tv_id = new_id()
    conn.execute(
        """
        INSERT INTO tv_screens (id, location_id, name, slug, show_images, show_sold_out, created_at)
        VALUES (?, ?, ?, ?, 1, 1, ?)
        """,
        (tv_id, location_id, "Uptown Main TV", "uptown-main-tv", created),
    )
    insert_default_settings(conn, tv_id, "Harbor Table Uptown")
    for category_id in category_ids.values():
        conn.execute(
            "INSERT INTO tv_screen_categories (id, tv_screen_id, category_id) VALUES (?, ?, ?)",
            (new_id(), tv_id, category_id),
        )


def insert_default_settings(conn: sqlite3.Connection, tv_screen_id: str, restaurant_name: str = "Harbor Table") -> None:
    conn.execute(
        """
        INSERT INTO display_settings (
          id, tv_screen_id, restaurant_name, background_color, text_color, accent_color,
          price_color, title_size, item_size, price_size, logo_url, background_image_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id(),
            tv_screen_id,
            restaurant_name,
            "#1f1713",
            "#fff7ed",
            "#f2b84b",
            "#8ee08e",
            72,
            30,
            32,
            "",
            "",
        ),
    )


def get_location_id(handler: SimpleHTTPRequestHandler) -> str | None:
    query = parse_qs(urlparse(handler.path).query)
    value = query.get("location_id", [None])[0]
    return value or None


def list_locations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM locations ORDER BY created_at, name").fetchall()
    return [dict(row) for row in rows]


def list_categories(conn: sqlite3.Connection, location_id: str | None = None) -> list[dict]:
    if location_id:
        rows = conn.execute(
            "SELECT * FROM categories WHERE location_id = ? ORDER BY sort_order, name",
            (location_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    return [dict(row) for row in rows]


def list_menu_items(conn: sqlite3.Connection, location_id: str | None = None) -> list[dict]:
    if location_id:
        rows = conn.execute(
            "SELECT * FROM menu_items WHERE location_id = ? ORDER BY sort_order, name",
            (location_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM menu_items ORDER BY sort_order, name").fetchall()
    return [normalize_item(row) for row in rows]


def normalize_item(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["available"] = bool(item["available"])
    return item


def normalize_tv(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    tv = dict(row)
    tv["show_images"] = bool(tv["show_images"])
    tv["show_sold_out"] = bool(tv["show_sold_out"])
    tv["category_ids"] = [
        entry["category_id"]
        for entry in conn.execute(
            "SELECT category_id FROM tv_screen_categories WHERE tv_screen_id = ?",
            (tv["id"],),
        ).fetchall()
    ]
    tv["item_ids"] = [
        entry["menu_item_id"]
        for entry in conn.execute(
            "SELECT menu_item_id FROM tv_screen_items WHERE tv_screen_id = ?",
            (tv["id"],),
        ).fetchall()
    ]
    return tv


def list_tvs(conn: sqlite3.Connection, location_id: str | None = None) -> list[dict]:
    if location_id:
        rows = conn.execute("SELECT * FROM tv_screens WHERE location_id = ? ORDER BY rowid", (location_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tv_screens ORDER BY rowid").fetchall()
    return [normalize_tv(conn, row) for row in rows]


def get_tv(conn: sqlite3.Connection, tv_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM tv_screens WHERE id = ?", (tv_id,)).fetchone()
    return normalize_tv(conn, row) if row else None


def get_settings(conn: sqlite3.Connection, tv_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM display_settings WHERE tv_screen_id = ?", (tv_id,)).fetchone()
    return row_to_dict(row)


def replace_assignments(conn: sqlite3.Connection, tv_id: str, category_ids: list[str], item_ids: list[str]) -> None:
    conn.execute("DELETE FROM tv_screen_categories WHERE tv_screen_id = ?", (tv_id,))
    conn.execute("DELETE FROM tv_screen_items WHERE tv_screen_id = ?", (tv_id,))
    for category_id in category_ids:
        conn.execute(
            "INSERT OR IGNORE INTO tv_screen_categories (id, tv_screen_id, category_id) VALUES (?, ?, ?)",
            (new_id(), tv_id, category_id),
        )
    for item_id in item_ids:
        conn.execute(
            "INSERT OR IGNORE INTO tv_screen_items (id, tv_screen_id, menu_item_id) VALUES (?, ?, ?)",
            (new_id(), tv_id, item_id),
        )


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/locations":
                return self.send_json(list_locations(connect()))
            if path == "/api/categories":
                return self.send_json(list_categories(connect(), get_location_id(self)))
            if path == "/api/menu-items":
                return self.send_json(list_menu_items(connect(), get_location_id(self)))
            if path == "/api/tv-screens":
                return self.send_json(list_tvs(connect(), get_location_id(self)))
            if match := re.fullmatch(r"/api/tv-screens/([^/]+)/settings", path):
                with connect() as conn:
                    settings = get_settings(conn, match.group(1))
                    if not settings:
                        return self.send_error_json("Settings not found", HTTPStatus.NOT_FOUND)
                    return self.send_json(settings)
            if match := re.fullmatch(r"/api/display/([^/]+)", path):
                return self.send_display(match.group(1))
            if path.startswith("/display/"):
                return self.serve_index()
            return super().do_GET()
        except Exception as exc:  # noqa: BLE001
            return self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = parse_json(self)
            if path == "/api/locations":
                return self.create_location(payload)
            if path == "/api/categories":
                return self.create_category(payload)
            if path == "/api/menu-items":
                return self.create_menu_item(payload)
            if path == "/api/tv-screens":
                return self.create_tv(payload)
            return self.send_error_json("Endpoint not found", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except sqlite3.IntegrityError as exc:
            return self.send_error_json(f"Database constraint failed: {exc}", HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = parse_json(self)
            if match := re.fullmatch(r"/api/locations/([^/]+)", path):
                return self.update_location(match.group(1), payload)
            if match := re.fullmatch(r"/api/categories/([^/]+)", path):
                return self.update_category(match.group(1), payload)
            if match := re.fullmatch(r"/api/menu-items/([^/]+)", path):
                return self.update_menu_item(match.group(1), payload)
            if match := re.fullmatch(r"/api/tv-screens/([^/]+)", path):
                return self.update_tv(match.group(1), payload)
            if match := re.fullmatch(r"/api/tv-screens/([^/]+)/settings", path):
                return self.update_settings(match.group(1), payload)
            return self.send_error_json("Endpoint not found", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except sqlite3.IntegrityError as exc:
            return self.send_error_json(f"Database constraint failed: {exc}", HTTPStatus.BAD_REQUEST)

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = parse_json(self)
            if match := re.fullmatch(r"/api/menu-items/([^/]+)/stock", path):
                return self.update_stock(match.group(1), payload)
            return self.send_error_json("Endpoint not found", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        try:
            if match := re.fullmatch(r"/api/locations/([^/]+)", path):
                return self.delete_row("locations", match.group(1))
            if match := re.fullmatch(r"/api/categories/([^/]+)", path):
                return self.delete_row("categories", match.group(1))
            if match := re.fullmatch(r"/api/menu-items/([^/]+)", path):
                return self.delete_row("menu_items", match.group(1))
            if match := re.fullmatch(r"/api/tv-screens/([^/]+)", path):
                return self.delete_row("tv_screens", match.group(1))
            return self.send_error_json("Endpoint not found", HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001
            return self.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def create_location(self, payload: dict) -> None:
        require(payload, "name")
        with connect() as conn:
            location_id = new_id()
            conn.execute(
                """
                INSERT INTO locations (id, name, address, phone, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    location_id,
                    payload["name"].strip(),
                    payload.get("address", "").strip(),
                    payload.get("phone", "").strip(),
                    now(),
                ),
            )
            row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
        self.send_json(dict(row), HTTPStatus.CREATED)

    def update_location(self, location_id: str, payload: dict) -> None:
        require(payload, "name")
        with connect() as conn:
            conn.execute(
                "UPDATE locations SET name = ?, address = ?, phone = ? WHERE id = ?",
                (
                    payload["name"].strip(),
                    payload.get("address", "").strip(),
                    payload.get("phone", "").strip(),
                    location_id,
                ),
            )
            row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
        if not row:
            return self.send_error_json("Location not found", HTTPStatus.NOT_FOUND)
        self.send_json(dict(row))

    def create_category(self, payload: dict) -> None:
        require(payload, "location_id", "name")
        with connect() as conn:
            category_id = new_id()
            conn.execute(
                "INSERT INTO categories (id, location_id, name, sort_order, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    category_id,
                    payload["location_id"],
                    payload["name"].strip(),
                    int(payload.get("sort_order") or 0),
                    now(),
                ),
            )
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        self.send_json(dict(row), HTTPStatus.CREATED)

    def update_category(self, category_id: str, payload: dict) -> None:
        require(payload, "name")
        with connect() as conn:
            conn.execute(
                "UPDATE categories SET name = ?, sort_order = ? WHERE id = ?",
                (payload["name"].strip(), int(payload.get("sort_order") or 0), category_id),
            )
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            return self.send_error_json("Category not found", HTTPStatus.NOT_FOUND)
        self.send_json(dict(row))

    def create_menu_item(self, payload: dict) -> None:
        require(payload, "location_id", "name", "category_id", "price")
        timestamp = now()
        with connect() as conn:
            item_id = new_id()
            conn.execute(
                """
                INSERT INTO menu_items (
                  id, location_id, name, description, category_id, price, image_url, available,
                  sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    payload["location_id"],
                    payload["name"].strip(),
                    payload.get("description", "").strip(),
                    payload["category_id"],
                    float(payload["price"]),
                    payload.get("image_url", "").strip(),
                    bool_row(payload.get("available", True)),
                    int(payload.get("sort_order") or 0),
                    timestamp,
                    timestamp,
                ),
            )
            row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        self.send_json(normalize_item(row), HTTPStatus.CREATED)

    def update_menu_item(self, item_id: str, payload: dict) -> None:
        require(payload, "name", "category_id", "price")
        with connect() as conn:
            conn.execute(
                """
                UPDATE menu_items
                SET name = ?, description = ?, category_id = ?, price = ?, image_url = ?,
                    available = ?, sort_order = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    payload.get("description", "").strip(),
                    payload["category_id"],
                    float(payload["price"]),
                    payload.get("image_url", "").strip(),
                    bool_row(payload.get("available", True)),
                    int(payload.get("sort_order") or 0),
                    now(),
                    item_id,
                ),
            )
            row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return self.send_error_json("Menu item not found", HTTPStatus.NOT_FOUND)
        self.send_json(normalize_item(row))

    def update_stock(self, item_id: str, payload: dict) -> None:
        if "available" not in payload:
            raise ValueError("Missing required field: available")
        with connect() as conn:
            conn.execute(
                "UPDATE menu_items SET available = ?, updated_at = ? WHERE id = ?",
                (bool_row(payload["available"]), now(), item_id),
            )
            row = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return self.send_error_json("Menu item not found", HTTPStatus.NOT_FOUND)
        self.send_json(normalize_item(row))

    def create_tv(self, payload: dict) -> None:
        require(payload, "location_id", "name")
        tv_id = new_id()
        slug = slugify(payload.get("slug") or payload["name"])
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO tv_screens (id, location_id, name, slug, show_images, show_sold_out, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tv_id,
                    payload["location_id"],
                    payload["name"].strip(),
                    slug,
                    bool_row(payload.get("show_images", True)),
                    bool_row(payload.get("show_sold_out", True)),
                    now(),
                ),
            )
            insert_default_settings(conn, tv_id)
            replace_assignments(conn, tv_id, payload.get("category_ids", []), payload.get("item_ids", []))
            tv = get_tv(conn, tv_id)
        self.send_json(tv, HTTPStatus.CREATED)

    def update_tv(self, tv_id: str, payload: dict) -> None:
        require(payload, "name")
        slug = slugify(payload.get("slug") or payload["name"])
        with connect() as conn:
            conn.execute(
                """
                UPDATE tv_screens
                SET name = ?, slug = ?, show_images = ?, show_sold_out = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    slug,
                    bool_row(payload.get("show_images", True)),
                    bool_row(payload.get("show_sold_out", True)),
                    tv_id,
                ),
            )
            replace_assignments(conn, tv_id, payload.get("category_ids", []), payload.get("item_ids", []))
            tv = get_tv(conn, tv_id)
        if not tv:
            return self.send_error_json("TV screen not found", HTTPStatus.NOT_FOUND)
        self.send_json(tv)

    def update_settings(self, tv_id: str, payload: dict) -> None:
        require(payload, "restaurant_name", "background_color", "text_color", "accent_color", "price_color")
        with connect() as conn:
            conn.execute(
                """
                UPDATE display_settings
                SET restaurant_name = ?, background_color = ?, text_color = ?, accent_color = ?,
                    price_color = ?, title_size = ?, item_size = ?, price_size = ?,
                    logo_url = ?, background_image_url = ?
                WHERE tv_screen_id = ?
                """,
                (
                    payload["restaurant_name"].strip(),
                    payload["background_color"],
                    payload["text_color"],
                    payload["accent_color"],
                    payload["price_color"],
                    int(payload.get("title_size") or 72),
                    int(payload.get("item_size") or 30),
                    int(payload.get("price_size") or 32),
                    payload.get("logo_url", "").strip(),
                    payload.get("background_image_url", "").strip(),
                    tv_id,
                ),
            )
            settings = get_settings(conn, tv_id)
        if not settings:
            return self.send_error_json("Settings not found", HTTPStatus.NOT_FOUND)
        self.send_json(settings)

    def delete_row(self, table: str, row_id: str) -> None:
        with connect() as conn:
            result = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        if result.rowcount == 0:
            return self.send_error_json("Record not found", HTTPStatus.NOT_FOUND)
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def send_display(self, slug: str) -> None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM tv_screens WHERE slug = ?", (slug,)).fetchone()
            if not row:
                return self.send_error_json("TV display not found", HTTPStatus.NOT_FOUND)
            tv = normalize_tv(conn, row)
            settings = get_settings(conn, tv["id"])
            categories = list_categories(conn, tv["location_id"])
            items = list_menu_items(conn, tv["location_id"])

        allowed_categories = set(tv["category_ids"])
        pinned_items = set(tv["item_ids"])

        if allowed_categories:
            categories = [category for category in categories if category["id"] in allowed_categories]
            items = [item for item in items if item["category_id"] in allowed_categories]

        if pinned_items:
            pinned = [item for item in list_menu_items(connect(), tv["location_id"]) if item["id"] in pinned_items]
            by_id = {item["id"]: item for item in items}
            for item in pinned:
                by_id[item["id"]] = item
            items = list(by_id.values())

        if not tv["show_sold_out"]:
            items = [item for item in items if item["available"]]

        items.sort(key=lambda item: (item.get("sort_order") or 0, item["name"]))
        self.send_json({"tv": tv, "settings": settings, "categories": categories, "items": items})

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: HTTPStatus) -> None:
        self.send_json({"error": message}, status)

    def serve_index(self) -> None:
        index = ROOT / "index.html"
        body = index.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 4173), Handler)
    print("Restaurant Digital TV Menu running at http://127.0.0.1:4173")
    server.serve_forever()


if __name__ == "__main__":
    main()
