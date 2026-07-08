# BillPilot AI

BillPilot AI is a prototype for an AI CFO that helps small and medium-sized businesses detect, track, approve, and pay bills while keeping owners in control of automation.

## Local MVP

Run the backend:

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:4173
```

The local MVP includes:

- Business cash and bill summary
- Persistent SQLite database
- Upcoming bill queue backed by API data
- Vendor AutoPay settings that update through the API
- Manual vendor creation
- Manual bill creation tied to saved vendors
- Local account connection and balance updates
- Simulated invoice upload and bill detection
- Batch payment for approved bills
- Simulated bill payment status updates
- Cash flow forecast
- Receipt vault backed by saved receipt records
- AI assistant responses from backend data

The app creates `billpilot.db` automatically on first run.

## Real Integration Notes

Actual bank connections, vendor portal access, and bill payment require production integrations and compliance controls. The next production steps are:

- Plaid Link for user-authorized bank accounts
- Stripe ACH or Dwolla for real payments
- OpenAI extraction for uploaded invoice PDFs
- S3 receipt storage
- Clerk or Auth0 authentication
- PostgreSQL for production data
- Audit logs and approval workflows before any real money movement

## Product Direction

Long term, BillPilot AI can grow into a business operating system for bill payments, vendor management, accounting integrations, reporting, payroll, inventory, and cash-flow intelligence.

## Suggested Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL
- AI: OpenAI API
- Authentication: Clerk or Auth0
- Bank connections: Plaid
- Payments: Stripe ACH or Dwolla
- Storage: Amazon S3
- Hosting: AWS
