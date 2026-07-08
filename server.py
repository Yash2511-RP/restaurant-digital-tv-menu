from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "billpilot.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              institution TEXT NOT NULL,
              account_type TEXT NOT NULL,
              balance_cents INTEGER NOT NULL,
              last_synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vendors (
              id INTEGER PRIMARY KEY,
              company_name TEXT NOT NULL,
              category TEXT NOT NULL,
              account_number TEXT NOT NULL,
              website TEXT NOT NULL,
              autopay_enabled INTEGER NOT NULL DEFAULT 0,
              payment_method TEXT NOT NULL,
              payment_schedule TEXT NOT NULL,
              max_payment_cents INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bills (
              id INTEGER PRIMARY KEY,
              vendor_id INTEGER NOT NULL REFERENCES vendors(id),
              amount_cents INTEGER NOT NULL,
              due_date TEXT NOT NULL,
              invoice_number TEXT NOT NULL,
              status TEXT NOT NULL,
              source TEXT NOT NULL,
              detected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS receipts (
              id INTEGER PRIMARY KEY,
              bill_id INTEGER REFERENCES bills(id),
              vendor_name TEXT NOT NULL,
              document_type TEXT NOT NULL,
              stored_path TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY,
              event_type TEXT NOT NULL,
              detail TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )

        vendor_count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
        if vendor_count:
            return

        now = utc_now()
        today = date.today()
        vendors = [
            (
                "City Electric",
                "Electric Utility",
                "CE-884921",
                "https://example.com/city-electric",
                0,
                "Operating Checking",
                "Pay 2 days early",
                250000,
            ),
            (
                "Metro Water",
                "Water",
                "MW-102938",
                "https://example.com/metro-water",
                1,
                "Operating Checking",
                "Pay on due date",
                120000,
            ),
            (
                "Frontier Internet",
                "Internet",
                "FI-72891",
                "https://example.com/frontier-internet",
                1,
                "Business Credit Card",
                "Pay 3 days early",
                60000,
            ),
            (
                "Restaurant Supply Co.",
                "Food Supplier",
                "RSC-558201",
                "https://example.com/restaurant-supply",
                0,
                "Operating Checking",
                "Manual approval",
                800000,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO vendors (
              company_name, category, account_number, website, autopay_enabled,
              payment_method, payment_schedule, max_payment_cents
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            vendors,
        )

        bills = [
            (1, 192000, today.isoformat(), "INV-4481", "approval_needed", "pdf_upload", now),
            (2, 92000, today.isoformat(), "MW-2026-0708", "ready_to_pay", "vendor_portal", now),
            (
                4,
                674000,
                (today + timedelta(days=2)).isoformat(),
                "RSC-88214",
                "scheduled",
                "business_email",
                now,
            ),
            (
                3,
                41200,
                (today + timedelta(days=6)).isoformat(),
                "FI-72891",
                "autopay_on",
                "vendor_portal",
                now,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO bills (
              vendor_id, amount_cents, due_date, invoice_number, status, source, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            bills,
        )

        conn.executemany(
            """
            INSERT INTO accounts (name, institution, account_type, balance_cents, last_synced_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("Operating Checking", "Demo Bank", "checking", 8426000, now),
                ("Tax Savings", "Demo Bank", "savings", 1840000, now),
                ("Business Rewards Card", "Demo Card", "credit_card", -321000, now),
            ],
        )

        conn.executemany(
            """
            INSERT INTO receipts (bill_id, vendor_name, document_type, stored_path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "City Electric", "Invoice PDF", "/receipts/city-electric-invoice.pdf", now),
                (None, "Landlord LLC", "Payment Confirmation", "/receipts/rent-confirmation.pdf", now),
                (3, "Restaurant Supply Co.", "Invoice", "/receipts/rsc-88214.pdf", now),
                (2, "Metro Water", "Statement PDF", "/receipts/metro-water.pdf", now),
            ],
        )


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    value = abs(cents) / 100
    return f"{sign}${value:,.0f}" if cents % 100 == 0 else f"{sign}${value:,.2f}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def status_label(status: str) -> str:
    labels = {
        "approval_needed": "Approval needed",
        "ready_to_pay": "Ready to pay",
        "scheduled": "Scheduled",
        "autopay_on": "AutoPay on",
        "paid": "Paid",
    }
    return labels.get(status, status.replace("_", " ").title())


def bill_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT bills.*, vendors.company_name, vendors.category
        FROM bills
        JOIN vendors ON vendors.id = bills.vendor_id
        ORDER BY bills.due_date ASC, bills.amount_cents DESC
        """
    ).fetchall()

    today = date.today()
    results = []
    for row in rows:
        due = date.fromisoformat(row["due_date"])
        if due == today:
            due_label = "Today"
        elif due == today + timedelta(days=1):
            due_label = "Tomorrow"
        else:
            due_label = due.strftime("%b %-d")

        results.append(
            {
                "id": row["id"],
                "vendor": row["company_name"],
                "category": row["category"],
                "amount": money(row["amount_cents"]),
                "amountCents": row["amount_cents"],
                "dueDate": row["due_date"],
                "due": due_label,
                "invoice": row["invoice_number"],
                "status": row["status"],
                "statusLabel": status_label(row["status"]),
                "source": row["source"],
                "warning": row["status"] == "approval_needed",
            }
        )
    return results


def dashboard(conn: sqlite3.Connection) -> dict:
    today = date.today()
    week_end = today + timedelta(days=7)
    accounts = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    bills = conn.execute("SELECT * FROM bills").fetchall()

    cash_cents = sum(
        row["balance_cents"]
        for row in accounts
        if row["account_type"] in {"checking", "savings"}
    )
    due_today_cents = sum(
        row["amount_cents"]
        for row in bills
        if row["due_date"] == today.isoformat() and row["status"] != "paid"
    )
    due_week_cents = sum(
        row["amount_cents"]
        for row in bills
        if today.isoformat() <= row["due_date"] <= week_end.isoformat()
        and row["status"] != "paid"
    )
    paid_cents = sum(row["amount_cents"] for row in bills if row["status"] == "paid")
    monthly_cents = sum(row["amount_cents"] for row in bills)

    return {
        "cashBalance": money(cash_cents),
        "dueToday": money(due_today_cents),
        "dueThisWeek": money(due_week_cents),
        "paidBills": money(paid_cents),
        "monthlySpending": money(monthly_cents),
        "projectedCashAfterWeek": money(cash_cents - due_week_cents),
        "recommendation": (
            "Approve City Electric only if the amount is expected. Metro Water is inside its "
            "AutoPay limit and can be paid today."
        ),
    }


def json_body(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw)


class BillPilotHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return super().do_GET()

        with connect() as conn:
            if path == "/api/dashboard":
                self.send_json(dashboard(conn))
                return
            if path == "/api/bills":
                self.send_json(bill_rows(conn))
                return
            if path == "/api/vendors":
                rows = conn.execute("SELECT * FROM vendors ORDER BY company_name").fetchall()
                self.send_json(
                    [
                        {
                            "id": row["id"],
                            "name": row["company_name"],
                            "category": row["category"],
                            "accountNumber": row["account_number"],
                            "website": row["website"],
                            "autopay": bool(row["autopay_enabled"]),
                            "paymentMethod": row["payment_method"],
                            "schedule": row["payment_schedule"],
                            "limit": money(row["max_payment_cents"]),
                        }
                        for row in rows
                    ]
                )
                return
            if path == "/api/receipts":
                rows = conn.execute("SELECT * FROM receipts ORDER BY created_at DESC").fetchall()
                self.send_json([dict(row) for row in rows])
                return

        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        with connect() as conn:
            vendor_match = re.fullmatch(r"/api/vendors/(\d+)/autopay", path)
            if vendor_match:
                payload = json_body(self)
                enabled = 1 if payload.get("enabled") else 0
                vendor_id = int(vendor_match.group(1))
                conn.execute(
                    "UPDATE vendors SET autopay_enabled = ? WHERE id = ?",
                    (enabled, vendor_id),
                )
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    (
                        "autopay_updated",
                        f"Vendor {vendor_id} AutoPay set to {bool(enabled)}",
                        utc_now(),
                    ),
                )
                self.send_json({"ok": True, "vendorId": vendor_id, "autopay": bool(enabled)})
                return

            bill_match = re.fullmatch(r"/api/bills/(\d+)/pay", path)
            if bill_match:
                bill_id = int(bill_match.group(1))
                conn.execute("UPDATE bills SET status = 'paid' WHERE id = ?", (bill_id,))
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    (
                        "payment_simulated",
                        f"Bill {bill_id} marked paid in demo mode",
                        utc_now(),
                    ),
                )
                self.send_json({"ok": True, "billId": bill_id, "status": "paid"})
                return

            if path == "/api/assistant":
                payload = json_body(self)
                question = str(payload.get("question", "")).lower()
                answer = answer_question(conn, question)
                self.send_json({"answer": answer})
                return

        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def answer_question(conn: sqlite3.Connection, question: str) -> str:
    bills = bill_rows(conn)
    dash = dashboard(conn)

    if "tomorrow" in question and "due" in question:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        due = [bill for bill in bills if bill["dueDate"] == tomorrow and bill["status"] != "paid"]
        if not due:
            return "No unpaid bills are due tomorrow."
        total = money(sum(bill["amountCents"] for bill in due))
        names = ", ".join(bill["vendor"] for bill in due)
        return f"{len(due)} unpaid bill(s) are due tomorrow: {names}, totaling {total}."

    if "utility" in question or "utilities" in question:
        rows = conn.execute(
            """
            SELECT SUM(bills.amount_cents)
            FROM bills
            JOIN vendors ON vendors.id = bills.vendor_id
            WHERE lower(vendors.category) LIKE '%utility%'
               OR lower(vendors.category) IN ('water', 'internet', 'phone', 'gas')
            """
        ).fetchone()
        return f"Utility spend currently tracked for this month is {money(rows[0] or 0)}."

    if "unpaid" in question or "invoice" in question:
        unpaid = [bill for bill in bills if bill["status"] != "paid"]
        total = money(sum(bill["amountCents"] for bill in unpaid))
        return f"There are {len(unpaid)} unpaid invoice(s), totaling {total}."

    if "cash" in question:
        return (
            f"Current cash is {dash['cashBalance']}. After this week's unpaid bills, "
            f"projected cash is {dash['projectedCashAfterWeek']}."
        )

    return (
        "I can answer questions about unpaid invoices, utility spend, due dates, "
        "projected cash, vendor limits, and receipt records."
    )


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 4173), BillPilotHandler)
    print("BillPilot AI running at http://127.0.0.1:4173")
    server.serve_forever()


if __name__ == "__main__":
    main()
