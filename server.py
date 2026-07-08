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


def cents_from_amount(value: object) -> int:
    try:
        amount = float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError as exc:
        raise ValueError("Amount must be a number") from exc
    if amount < 0:
        raise ValueError("Amount must be positive")
    return round(amount * 100)


def deduct_from_operating_cash(conn: sqlite3.Connection, amount_cents: int) -> None:
    account = conn.execute(
        "SELECT id FROM accounts WHERE account_type IN ('checking', 'savings') ORDER BY id LIMIT 1"
    ).fetchone()
    if account is None:
        return
    conn.execute(
        "UPDATE accounts SET balance_cents = balance_cents - ? WHERE id = ?",
        (amount_cents, account["id"]),
    )


def create_payment_receipt(conn: sqlite3.Connection, bill_id: int) -> None:
    row = conn.execute(
        """
        SELECT bills.invoice_number, vendors.company_name
        FROM bills
        JOIN vendors ON vendors.id = bills.vendor_id
        WHERE bills.id = ?
        """,
        (bill_id,),
    ).fetchone()
    if row is None:
        return
    conn.execute(
        """
        INSERT INTO receipts (bill_id, vendor_name, document_type, stored_path, created_at)
        VALUES (?, ?, 'Payment Confirmation', ?, ?)
        """,
        (
            bill_id,
            row["company_name"],
            f"/receipts/payment-confirmation-{bill_id}.pdf",
            utc_now(),
        ),
    )


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


def require_text(payload: dict, field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


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

    def send_error_json(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.send_json({"error": message}, status)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return super().do_GET()

        with connect() as conn:
            if path == "/api/dashboard":
                self.send_json(dashboard(conn))
                return
            if path == "/api/accounts":
                rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
                self.send_json(
                    [
                        {
                            "id": row["id"],
                            "name": row["name"],
                            "institution": row["institution"],
                            "accountType": row["account_type"],
                            "balance": money(row["balance_cents"]),
                            "lastSyncedAt": row["last_synced_at"],
                        }
                        for row in rows
                    ]
                )
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
            if path == "/api/accounts":
                try:
                    payload = json_body(self)
                    name = require_text(payload, "name")
                    institution = require_text(payload, "institution")
                    account_type = require_text(payload, "accountType")
                    if account_type not in {"checking", "savings", "credit_card"}:
                        raise ValueError("Unsupported account type")
                    balance_cents = cents_from_amount(require_text(payload, "balance"))
                except ValueError as exc:
                    self.send_error_json(str(exc))
                    return

                cursor = conn.execute(
                    """
                    INSERT INTO accounts (
                      name, institution, account_type, balance_cents, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, institution, account_type, balance_cents, utc_now()),
                )
                account_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    ("account_connected", f"Account {account_id} connected: {name}", utc_now()),
                )
                self.send_json({"ok": True, "accountId": account_id}, HTTPStatus.CREATED)
                return

            if path == "/api/pay-approved":
                rows = conn.execute(
                    """
                    SELECT id, amount_cents
                    FROM bills
                    WHERE status IN ('ready_to_pay', 'scheduled', 'autopay_on')
                    """
                ).fetchall()
                total_cents = sum(row["amount_cents"] for row in rows)
                bill_ids = [row["id"] for row in rows]

                if bill_ids:
                    placeholders = ",".join("?" for _ in bill_ids)
                    conn.execute(
                        f"UPDATE bills SET status = 'paid' WHERE id IN ({placeholders})",
                        bill_ids,
                    )
                    deduct_from_operating_cash(conn, total_cents)
                    for bill_id in bill_ids:
                        create_payment_receipt(conn, bill_id)

                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    (
                        "approved_payments_simulated",
                        f"{len(bill_ids)} approved bill(s) marked paid",
                        utc_now(),
                    ),
                )
                self.send_json(
                    {
                        "ok": True,
                        "paidCount": len(bill_ids),
                        "totalPaid": money(total_cents),
                    }
                )
                return

            if path == "/api/bill-detections":
                try:
                    payload = json_body(self)
                    filename = require_text(payload, "filename")
                except ValueError as exc:
                    self.send_error_json(str(exc))
                    return

                vendor_name = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
                vendor_name = vendor_name.title() or "Uploaded Invoice"
                vendor = conn.execute(
                    "SELECT id, company_name FROM vendors WHERE lower(company_name) = lower(?)",
                    (vendor_name,),
                ).fetchone()
                if vendor is None:
                    cursor = conn.execute(
                        """
                        INSERT INTO vendors (
                          company_name, category, account_number, website, autopay_enabled,
                          payment_method, payment_schedule, max_payment_cents
                        ) VALUES (?, 'Uploaded Invoice', 'Detected', 'https://example.com', 0,
                          'Operating Checking', 'Manual approval', 500000)
                        """,
                        (vendor_name,),
                    )
                    vendor_id = cursor.lastrowid
                else:
                    vendor_id = vendor["id"]

                amount_cents = 25000
                due_date = (date.today() + timedelta(days=7)).isoformat()
                invoice_number = f"UPLOAD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
                cursor = conn.execute(
                    """
                    INSERT INTO bills (
                      vendor_id, amount_cents, due_date, invoice_number, status, source, detected_at
                    ) VALUES (?, ?, ?, ?, 'approval_needed', 'pdf_upload', ?)
                    """,
                    (vendor_id, amount_cents, due_date, invoice_number, utc_now()),
                )
                bill_id = cursor.lastrowid
                conn.execute(
                    """
                    INSERT INTO receipts (bill_id, vendor_name, document_type, stored_path, created_at)
                    VALUES (?, ?, 'Uploaded Invoice', ?, ?)
                    """,
                    (bill_id, vendor_name, f"/receipts/{filename}", utc_now()),
                )
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    ("bill_detected", f"Detected bill {bill_id} from {filename}", utc_now()),
                )
                self.send_json(
                    {
                        "ok": True,
                        "billId": bill_id,
                        "vendor": vendor_name,
                        "amount": money(amount_cents),
                    },
                    HTTPStatus.CREATED,
                )
                return

            if path == "/api/vendors":
                try:
                    payload = json_body(self)
                    company_name = require_text(payload, "companyName")
                    category = require_text(payload, "category")
                    account_number = str(payload.get("accountNumber", "")).strip() or "Manual"
                    website = str(payload.get("website", "")).strip() or "https://example.com"
                    payment_method = (
                        str(payload.get("paymentMethod", "")).strip() or "Operating Checking"
                    )
                    payment_schedule = (
                        str(payload.get("paymentSchedule", "")).strip() or "Manual approval"
                    )
                    max_payment_cents = cents_from_amount(payload.get("maxPayment") or 0)
                except ValueError as exc:
                    self.send_error_json(str(exc))
                    return

                cursor = conn.execute(
                    """
                    INSERT INTO vendors (
                      company_name, category, account_number, website, autopay_enabled,
                      payment_method, payment_schedule, max_payment_cents
                    ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        company_name,
                        category,
                        account_number,
                        website,
                        payment_method,
                        payment_schedule,
                        max_payment_cents,
                    ),
                )
                vendor_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    ("vendor_created", f"Vendor {vendor_id} created: {company_name}", utc_now()),
                )
                self.send_json({"ok": True, "vendorId": vendor_id}, HTTPStatus.CREATED)
                return

            if path == "/api/bills":
                try:
                    payload = json_body(self)
                    vendor_id = int(require_text(payload, "vendorId"))
                    amount_cents = cents_from_amount(require_text(payload, "amount"))
                    due_date = require_text(payload, "dueDate")
                    date.fromisoformat(due_date)
                    invoice_number = require_text(payload, "invoiceNumber")
                    status = str(payload.get("status", "approval_needed")).strip()
                    if status not in {"approval_needed", "ready_to_pay", "scheduled"}:
                        raise ValueError("Unsupported bill status")
                except ValueError as exc:
                    self.send_error_json(str(exc))
                    return

                vendor = conn.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
                if vendor is None:
                    self.send_error_json("Vendor not found", HTTPStatus.NOT_FOUND)
                    return

                cursor = conn.execute(
                    """
                    INSERT INTO bills (
                      vendor_id, amount_cents, due_date, invoice_number, status, source, detected_at
                    ) VALUES (?, ?, ?, ?, ?, 'manual_entry', ?)
                    """,
                    (vendor_id, amount_cents, due_date, invoice_number, status, utc_now()),
                )
                bill_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO audit_events (event_type, detail, created_at) VALUES (?, ?, ?)",
                    ("bill_created", f"Bill {bill_id} created from manual entry", utc_now()),
                )
                self.send_json({"ok": True, "billId": bill_id}, HTTPStatus.CREATED)
                return

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
                bill = conn.execute(
                    "SELECT amount_cents, status FROM bills WHERE id = ?",
                    (bill_id,),
                ).fetchone()
                if bill is None:
                    self.send_error_json("Bill not found", HTTPStatus.NOT_FOUND)
                    return
                if bill["status"] != "paid":
                    deduct_from_operating_cash(conn, bill["amount_cents"])
                    create_payment_receipt(conn, bill_id)
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
