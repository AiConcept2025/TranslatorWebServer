# Payments API - Common Usage Scenarios

Real-world usage scenarios with step-by-step instructions and code examples.

---

## Table of Contents

1. [Admin Scenarios](#admin-scenarios)
2. [Company Management Scenarios](#company-management-scenarios)
3. [Refund Scenarios](#refund-scenarios)
4. [Reporting Scenarios](#reporting-scenarios)
5. [Integration Scenarios](#integration-scenarios)
6. [Error Handling Scenarios](#error-handling-scenarios)

---

## Admin Scenarios

### Scenario 1: Admin Dashboard - View All Recent Payments

**Goal:** Admin wants to see the latest 20 payments across all companies

**Use Case:** Dashboard overview, recent activity monitoring

**Steps:**

1. **Authenticate as admin:**
```bash
# Login and get admin token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/admin/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin_password"
  }' | jq -r '.access_token')
```

2. **Fetch recent payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=20&sort_by=payment_date&sort_order=desc" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data.payments[] | {company: .company_name, amount: .amount, status: .payment_status, date: .payment_date}'
```

3. **Expected Output:**
```json
{
  "company": "Acme Health LLC",
  "amount": 1299,
  "status": "COMPLETED",
  "date": "2025-10-24T01:17:54.544Z"
}
{
  "company": "TechCorp Inc",
  "amount": 2499,
  "status": "COMPLETED",
  "date": "2025-10-24T02:30:15.123Z"
}
```

**Python Example:**
```python
import requests
from datetime import datetime

class AdminDashboard:
    def __init__(self, admin_token: str):
        self.base_url = "http://localhost:8000"
        self.headers = {
            "Authorization": f"Bearer {admin_token}"
        }

    def get_recent_payments(self, limit: int = 20):
        """Get most recent payments across all companies"""
        response = requests.get(
            f"{self.base_url}/api/v1/payments",
            headers=self.headers,
            params={
                "limit": limit,
                "sort_by": "payment_date",
                "sort_order": "desc"
            }
        )
        response.raise_for_status()
        return response.json()["data"]["payments"]

    def display_recent_activity(self):
        """Display recent payment activity"""
        payments = self.get_recent_payments(limit=10)

        print("Recent Payment Activity")
        print("=" * 80)

        for payment in payments:
            amount_dollars = payment["amount"] / 100
            date = datetime.fromisoformat(payment["payment_date"].rstrip('Z'))

            print(f"{date.strftime('%Y-%m-%d %H:%M')} | "
                  f"{payment['company_name']:<30} | "
                  f"${amount_dollars:>8.2f} | "
                  f"{payment['payment_status']:<10}")

        print("=" * 80)

# Usage
dashboard = AdminDashboard(admin_token="your_token_here")
dashboard.display_recent_activity()
```

---

### Scenario 2: Admin Filters Payments by Status

**Goal:** Admin wants to review all failed payments for troubleshooting

**Steps:**

1. **Get all failed payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=FAILED&limit=100" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data'
```

2. **Analyze failures:**
```bash
# Group by company
curl -X GET "http://localhost:8000/api/v1/payments?status=FAILED" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data.payments | group_by(.company_name) | map({company: .[0].company_name, count: length})'
```

3. **Export to CSV:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=FAILED" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data.payments[] | [.company_name, .user_email, .amount, .payment_date] | @csv' \
  > failed_payments.csv
```

**Python Example:**
```python
def analyze_failed_payments(admin_token: str):
    """Analyze failed payments and generate report"""

    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(
        "http://localhost:8000/api/v1/payments",
        headers=headers,
        params={"status": "FAILED", "limit": 100}
    )

    failed_payments = response.json()["data"]["payments"]

    # Group by company
    by_company = {}
    for payment in failed_payments:
        company = payment["company_name"]
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(payment)

    # Generate report
    print("Failed Payments Report")
    print("=" * 60)

    for company, payments in by_company.items():
        total_failed_amount = sum(p["amount"] for p in payments)
        print(f"\n{company}:")
        print(f"  Failed Count: {len(payments)}")
        print(f"  Total Amount: ${total_failed_amount / 100:.2f}")
        print(f"  Emails: {', '.join(set(p['user_email'] for p in payments))}")

# Usage
analyze_failed_payments(admin_token)
```

---

### Scenario 3: Recording a Subscription Payment After Square Webhook

**Goal:** Admin receives Square webhook confirming payment and records it in the database

**Context:** Square webhook received, subscription payment successful

**Steps:**

1. **Verify subscription exists:**
```bash
# Check subscription in MongoDB (via admin tools or MCP)
SUBSCRIPTION_ID="690023c7eb2bceb90e274133"
```

2. **Extract webhook data:**
```python
# Webhook handler (simplified)
@app.post("/webhooks/square")
async def handle_square_webhook(request: Request):
    """Handle Square payment webhook"""

    event = await request.json()
    event_type = event.get("type")

    if event_type == "payment.updated":
        payment_data = event["data"]["object"]["payment"]

        # Extract details
        square_payment_id = payment_data["id"]
        square_order_id = payment_data.get("order_id")
        amount = payment_data["amount_money"]["amount"]
        status = payment_data["status"]

        # Get subscription from order metadata
        subscription_id = payment_data.get("note") or \
                         payment_data.get("buyer_email_address")

        # Record payment
        await record_subscription_payment(
            square_payment_id=square_payment_id,
            square_order_id=square_order_id,
            subscription_id=subscription_id,
            amount=amount,
            status=status
        )

    return {"status": "processed"}
```

3. **Create payment record:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_webhook_001",
    "square_order_id": "sq_order_webhook_001",
    "user_email": "admin@acme.com",
    "amount": 9000,
    "payment_status": "COMPLETED",
    "card_brand": "VISA",
    "card_last_4": "1234"
  }'
```

4. **Verify payment recorded:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_webhook_001" \
  | jq '.'
```

**Complete Python Example:**
```python
from typing import Dict, Any
import requests
from datetime import datetime

class SubscriptionPaymentRecorder:
    def __init__(self, api_url: str, admin_token: str):
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }

    def record_from_square_webhook(self, webhook_data: Dict[str, Any]):
        """Record subscription payment from Square webhook"""

        # Extract payment details
        payment = webhook_data["data"]["object"]["payment"]

        square_payment_id = payment["id"]
        square_order_id = payment.get("order_id")
        amount = payment["amount_money"]["amount"]

        # Extract metadata (subscription info)
        note = payment.get("note", "")
        # Assuming note contains: "subscription_id:690023c7eb2bceb90e274133,company:Acme Corp"

        metadata = dict(item.split(":") for item in note.split(","))
        subscription_id = metadata.get("subscription_id")
        company_name = metadata.get("company")

        # Get buyer info
        user_email = payment.get("buyer_email_address", "unknown@example.com")

        # Card details
        card = payment.get("card_details", {}).get("card", {})
        card_brand = card.get("card_brand")
        card_last_4 = card.get("last_4")

        # Create payment record
        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": square_payment_id,
            "square_order_id": square_order_id,
            "user_email": user_email,
            "amount": amount,
            "payment_status": "COMPLETED",
            "payment_method": "card",
            "card_brand": card_brand,
            "card_last_4": card_last_4
        }

        response = requests.post(
            f"{self.api_url}/api/v1/payments/subscription",
            headers=self.headers,
            json=payment_data
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Payment recorded: {result['data']['_id']}")
            return result["data"]
        else:
            print(f"❌ Failed to record payment: {response.text}")
            raise Exception(f"Payment recording failed: {response.status_code}")

# Usage
recorder = SubscriptionPaymentRecorder(
    api_url="http://localhost:8000",
    admin_token="your_admin_token"
)

# Simulate webhook
webhook_data = {
    "type": "payment.updated",
    "data": {
        "object": {
            "payment": {
                "id": "sq_payment_webhook_123",
                "order_id": "sq_order_webhook_123",
                "amount_money": {"amount": 9000, "currency": "USD"},
                "status": "COMPLETED",
                "note": "subscription_id:690023c7eb2bceb90e274133,company:Acme Corp",
                "buyer_email_address": "admin@acme.com",
                "card_details": {
                    "card": {
                        "card_brand": "VISA",
                        "last_4": "1234"
                    }
                }
            }
        }
    }
}

payment = recorder.record_from_square_webhook(webhook_data)
```

---

## Company Management Scenarios

### Scenario 4: Company Views Payment History

**Goal:** Company admin wants to review their payment history for the last 3 months

**Steps:**

1. **Get all company payments:**
```bash
COMPANY="Acme Health LLC"
curl -X GET "http://localhost:8000/api/v1/payments/company/${COMPANY// /%20}" \
  | jq '.data.payments'
```

2. **Filter by date (in application layer):**
```python
from datetime import datetime, timedelta

def get_recent_company_payments(company_name: str, days: int = 90):
    """Get company payments for the last N days"""

    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}",
        params={"limit": 100}
    )

    all_payments = response.json()["data"]["payments"]

    # Filter by date
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    recent_payments = [
        p for p in all_payments
        if datetime.fromisoformat(p["payment_date"].rstrip('Z')) >= cutoff_date
    ]

    return recent_payments

# Usage
payments = get_recent_company_payments("Acme Health LLC", days=90)
print(f"Found {len(payments)} payments in the last 90 days")
```

3. **Generate payment summary:**
```python
def generate_payment_summary(company_name: str):
    """Generate comprehensive payment summary for a company"""

    # Get payments
    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}"
    )

    payments = response.json()["data"]["payments"]

    # Calculate statistics
    total_count = len(payments)
    total_amount = sum(p["amount"] for p in payments)
    completed_count = sum(1 for p in payments if p["payment_status"] == "COMPLETED")
    refunded_count = sum(1 for p in payments if p["payment_status"] == "REFUNDED")

    # Total refunded amount
    total_refunded = sum(
        sum(r["amount"] for r in p["refunds"])
        for p in payments
    )

    # Print summary
    print(f"\nPayment Summary for {company_name}")
    print("=" * 60)
    print(f"Total Payments:     {total_count}")
    print(f"Completed:          {completed_count}")
    print(f"Refunded:           {refunded_count}")
    print(f"Total Amount:       ${total_amount / 100:.2f}")
    print(f"Total Refunded:     ${total_refunded / 100:.2f}")
    print(f"Net Amount:         ${(total_amount - total_refunded) / 100:.2f}")
    print("=" * 60)

# Usage
generate_payment_summary("Acme Health LLC")
```

---

### Scenario 5: Company Tracks Subscription Payments

**Goal:** Company wants to see all payments linked to their subscription

**Steps:**

1. **Get company payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Translation%20Corp" \
  | jq '.data.payments[] | select(.subscription_id != null) | {id: ._id, subscription: .subscription_id, amount: .amount, date: .payment_date}'
```

2. **Python example with subscription tracking:**
```python
def track_subscription_payments(company_name: str, subscription_id: str):
    """Track all payments for a specific subscription"""

    # Get all company payments
    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}"
    )

    all_payments = response.json()["data"]["payments"]

    # Filter by subscription
    subscription_payments = [
        p for p in all_payments
        if p.get("subscription_id") == subscription_id
    ]

    # Sort by date
    subscription_payments.sort(
        key=lambda p: p["payment_date"],
        reverse=True
    )

    # Display
    print(f"\nSubscription Payments for {subscription_id}")
    print("=" * 80)
    print(f"{'Date':<20} {'Amount':<15} {'Status':<15} {'Square ID':<30}")
    print("-" * 80)

    for payment in subscription_payments:
        date = datetime.fromisoformat(payment["payment_date"].rstrip('Z'))
        amount = payment["amount"] / 100

        print(f"{date.strftime('%Y-%m-%d %H:%M'):<20} "
              f"${amount:<14.2f} "
              f"{payment['payment_status']:<15} "
              f"{payment['square_payment_id']:<30}")

    print("-" * 80)
    print(f"Total Payments: {len(subscription_payments)}")
    print(f"Total Amount: ${sum(p['amount'] for p in subscription_payments) / 100:.2f}")

# Usage
track_subscription_payments(
    company_name="Acme Translation Corp",
    subscription_id="690023c7eb2bceb90e274133"
)
```

---

## Refund Scenarios

### Scenario 6: Processing a Partial Refund

**Goal:** Customer requests partial refund for overpayment

**Context:** Payment of $50.00 was made, customer should have been charged $45.00

**Steps:**

1. **Find the payment:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_overpayment" \
  | jq '.'
```

2. **Verify payment amount:**
```json
{
  "_id": "68fad3c2a0f41c24037c4850",
  "amount": 5000,
  "payment_status": "COMPLETED",
  "refunds": []
}
```

3. **Calculate refund amount:**
```bash
# Refund $5.00 (500 cents)
REFUND_AMOUNT=500
```

4. **Process refund:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/sq_payment_overpayment/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_overpayment_001",
    "amount": 500,
    "currency": "USD",
    "idempotency_key": "rfd_unique_overpayment_001"
  }' \
  | jq '.'
```

5. **Verify refund:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_overpayment" \
  | jq '.refunds'
```

**Python Example:**
```python
import uuid

def process_partial_refund(
    square_payment_id: str,
    refund_amount_cents: int,
    reason: str = "Customer request"
):
    """Process a partial refund for a payment"""

    # Get payment details
    response = requests.get(
        f"http://localhost:8000/api/v1/payments/square/{square_payment_id}"
    )

    if response.status_code == 404:
        print(f"❌ Payment not found: {square_payment_id}")
        return None

    payment = response.json()

    # Verify refund amount is valid
    payment_amount = payment["amount"]
    existing_refunds = payment.get("refunds", [])
    total_refunded = sum(r["amount"] for r in existing_refunds)
    remaining = payment_amount - total_refunded

    if refund_amount_cents > remaining:
        print(f"❌ Refund amount ({refund_amount_cents}) exceeds remaining amount ({remaining})")
        return None

    # Generate unique IDs
    refund_id = f"rfn_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"rfd_{uuid.uuid4()}"

    # Process refund
    refund_data = {
        "refund_id": refund_id,
        "amount": refund_amount_cents,
        "currency": "USD",
        "idempotency_key": idempotency_key
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/payments/{square_payment_id}/refund",
        json=refund_data
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Refund processed: {refund_amount_cents / 100:.2f} USD")
        print(f"   Refund ID: {refund_id}")
        print(f"   Remaining: ${(remaining - refund_amount_cents) / 100:.2f}")
        return result
    else:
        print(f"❌ Refund failed: {response.text}")
        return None

# Usage
process_partial_refund(
    square_payment_id="sq_payment_overpayment",
    refund_amount_cents=500,
    reason="Overpayment correction"
)
```

---

### Scenario 7: Full Refund for Cancelled Subscription

**Goal:** Customer cancels subscription, needs full refund for current period

**Steps:**

1. **Get most recent payment:**
```python
def get_latest_payment(company_name: str, subscription_id: str):
    """Get the most recent payment for a subscription"""

    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}"
    )

    payments = response.json()["data"]["payments"]

    # Filter by subscription
    sub_payments = [
        p for p in payments
        if p.get("subscription_id") == subscription_id
    ]

    if not sub_payments:
        return None

    # Get most recent
    latest = max(sub_payments, key=lambda p: p["payment_date"])
    return latest
```

2. **Process full refund:**
```python
def full_refund_for_cancellation(company_name: str, subscription_id: str):
    """Process full refund for subscription cancellation"""

    # Get latest payment
    payment = get_latest_payment(company_name, subscription_id)

    if not payment:
        print(f"❌ No payments found for subscription {subscription_id}")
        return

    square_payment_id = payment["square_payment_id"]
    full_amount = payment["amount"]

    # Check if already refunded
    if payment.get("refunds"):
        print(f"⚠️  Payment already has refunds")
        total_refunded = sum(r["amount"] for r in payment["refunds"])
        if total_refunded >= full_amount:
            print(f"❌ Already fully refunded")
            return

    # Process full refund
    refund_id = f"rfn_cancellation_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"rfd_{uuid.uuid4()}"

    refund_data = {
        "refund_id": refund_id,
        "amount": full_amount,
        "currency": "USD",
        "idempotency_key": idempotency_key
    }

    response = requests.post(
        f"http://localhost:8000/api/v1/payments/{square_payment_id}/refund",
        json=refund_data
    )

    if response.status_code == 200:
        print(f"✅ Full refund processed: ${full_amount / 100:.2f}")
        print(f"   Payment ID: {payment['_id']}")
        print(f"   Refund ID: {refund_id}")
    else:
        print(f"❌ Refund failed: {response.text}")

# Usage
full_refund_for_cancellation(
    company_name="Acme Translation Corp",
    subscription_id="690023c7eb2bceb90e274133"
)
```

---

## Reporting Scenarios

### Scenario 8: Generate Monthly Payment Report

**Goal:** Generate monthly payment report for accounting

**Steps:**

```python
from datetime import datetime, timedelta
import csv

def generate_monthly_report(company_name: str, year: int, month: int):
    """Generate monthly payment report"""

    # Get all company payments
    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}",
        params={"limit": 500}
    )

    all_payments = response.json()["data"]["payments"]

    # Filter by month
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month + 1, 1)

    month_payments = [
        p for p in all_payments
        if month_start <= datetime.fromisoformat(p["payment_date"].rstrip('Z')) < month_end
    ]

    # Generate CSV report
    filename = f"payment_report_{company_name.replace(' ', '_')}_{year}_{month:02d}.csv"

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow([
            'Date', 'Payment ID', 'Square Payment ID', 'User Email',
            'Amount (USD)', 'Status', 'Refunded (USD)', 'Net Amount (USD)'
        ])

        # Data rows
        for payment in month_payments:
            date = datetime.fromisoformat(payment["payment_date"].rstrip('Z'))
            amount = payment["amount"] / 100
            refunded = sum(r["amount"] for r in payment.get("refunds", [])) / 100
            net = amount - refunded

            writer.writerow([
                date.strftime('%Y-%m-%d %H:%M:%S'),
                payment["_id"],
                payment["square_payment_id"],
                payment["user_email"],
                f"{amount:.2f}",
                payment["payment_status"],
                f"{refunded:.2f}",
                f"{net:.2f}"
            ])

        # Summary row
        total_amount = sum(p["amount"] for p in month_payments) / 100
        total_refunded = sum(
            sum(r["amount"] for r in p.get("refunds", []))
            for p in month_payments
        ) / 100
        net_total = total_amount - total_refunded

        writer.writerow([])
        writer.writerow(['TOTAL', '', '', '', f"{total_amount:.2f}", '', f"{total_refunded:.2f}", f"{net_total:.2f}"])

    print(f"✅ Report generated: {filename}")
    print(f"   Payments: {len(month_payments)}")
    print(f"   Total Amount: ${total_amount:.2f}")
    print(f"   Total Refunded: ${total_refunded:.2f}")
    print(f"   Net Revenue: ${net_total:.2f}")

# Usage
generate_monthly_report("Acme Health LLC", year=2025, month=10)
```

---

### Scenario 9: Payment Statistics Dashboard

**Goal:** Create a payment statistics dashboard

**Steps:**

```python
def payment_statistics_dashboard(company_name: str):
    """Generate comprehensive payment statistics"""

    # Get payment stats from API
    response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}/stats"
    )

    stats = response.json()["data"]

    # Get detailed payments for additional metrics
    payments_response = requests.get(
        f"http://localhost:8000/api/v1/payments/company/{company_name}",
        params={"limit": 1000}
    )

    payments = payments_response.json()["data"]["payments"]

    # Calculate additional metrics
    refunded_count = sum(1 for p in payments if p["payment_status"] == "REFUNDED")
    avg_payment = stats["total_amount_dollars"] / stats["total_payments"] if stats["total_payments"] > 0 else 0

    # Payment distribution by status
    status_counts = {}
    for payment in payments:
        status = payment["payment_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    # Print dashboard
    print("\n" + "=" * 80)
    print(f"PAYMENT STATISTICS DASHBOARD - {company_name}")
    print("=" * 80)

    print(f"\n📊 Overview")
    print(f"   Total Payments:        {stats['total_payments']}")
    print(f"   Total Revenue:         ${stats['total_amount_dollars']:.2f}")
    print(f"   Average Payment:       ${avg_payment:.2f}")

    print(f"\n✅ Success Metrics")
    print(f"   Completed Payments:    {stats['completed_payments']}")
    print(f"   Success Rate:          {stats['success_rate']:.2f}%")

    print(f"\n❌ Failed Transactions")
    print(f"   Failed Payments:       {stats['failed_payments']}")
    print(f"   Failure Rate:          {(100 - stats['success_rate']):.2f}%")

    print(f"\n💸 Refunds")
    print(f"   Refunded Payments:     {refunded_count}")

    print(f"\n📈 Payment Status Distribution")
    for status, count in sorted(status_counts.items()):
        percentage = (count / stats['total_payments'] * 100) if stats['total_payments'] > 0 else 0
        print(f"   {status:<15}        {count:>5} ({percentage:>5.1f}%)")

    print("=" * 80 + "\n")

# Usage
payment_statistics_dashboard("Acme Health LLC")
```

---

## Integration Scenarios

### Scenario 10: Webhook Integration

**Goal:** Integrate Square webhooks with payment API

**Complete Implementation:**

```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json

app = FastAPI()

# Square webhook configuration
SQUARE_WEBHOOK_SIGNATURE_KEY = "your_square_webhook_signature_key"
ADMIN_TOKEN = "your_admin_token"

async def verify_square_signature(payload: bytes, signature: str) -> bool:
    """Verify Square webhook signature"""
    computed_signature = hmac.new(
        SQUARE_WEBHOOK_SIGNATURE_KEY.encode(),
        payload,
        hashlib.sha256
    ).digest().hex()

    return hmac.compare_digest(computed_signature, signature)

@app.post("/webhooks/square/payments")
async def handle_square_payment_webhook(request: Request):
    """Handle Square payment webhooks and record payments"""

    # Get signature
    signature = request.headers.get("x-square-signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    # Get payload
    payload = await request.body()

    # Verify signature
    if not await verify_square_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event = json.loads(payload)
    event_type = event.get("type")

    if event_type == "payment.updated":
        await handle_payment_updated(event)
    elif event_type == "refund.updated":
        await handle_refund_updated(event)

    return {"status": "processed"}

async def handle_payment_updated(event: dict):
    """Handle payment.updated webhook"""

    payment = event["data"]["object"]["payment"]

    # Extract payment details
    square_payment_id = payment["id"]
    square_order_id = payment.get("order_id")
    amount = payment["amount_money"]["amount"]
    status = payment["status"]

    # Extract metadata
    note = payment.get("note", "")
    metadata = parse_payment_metadata(note)

    # Only record if status is COMPLETED
    if status == "COMPLETED":
        # Create payment record
        payment_data = {
            "company_name": metadata.get("company_name"),
            "subscription_id": metadata.get("subscription_id"),
            "square_payment_id": square_payment_id,
            "square_order_id": square_order_id,
            "user_email": payment.get("buyer_email_address", "unknown@example.com"),
            "amount": amount,
            "payment_status": "COMPLETED"
        }

        # Add card details if available
        if "card_details" in payment:
            card = payment["card_details"].get("card", {})
            payment_data["card_brand"] = card.get("card_brand")
            payment_data["card_last_4"] = card.get("last_4")

        # Send to payments API
        response = requests.post(
            "http://localhost:8000/api/v1/payments/subscription",
            headers={
                "Authorization": f"Bearer {ADMIN_TOKEN}",
                "Content-Type": "application/json"
            },
            json=payment_data
        )

        if response.status_code == 201:
            print(f"✅ Payment recorded: {response.json()['data']['_id']}")
        else:
            print(f"❌ Failed to record payment: {response.text}")

async def handle_refund_updated(event: dict):
    """Handle refund.updated webhook"""

    refund = event["data"]["object"]["refund"]

    # Extract refund details
    refund_id = refund["id"]
    square_payment_id = refund["payment_id"]
    amount = refund["amount_money"]["amount"]
    status = refund["status"]

    if status == "COMPLETED":
        # Process refund via API
        refund_data = {
            "refund_id": refund_id,
            "amount": amount,
            "currency": "USD",
            "idempotency_key": refund.get("idempotency_key", f"webhook_{refund_id}")
        }

        response = requests.post(
            f"http://localhost:8000/api/v1/payments/{square_payment_id}/refund",
            json=refund_data
        )

        if response.status_code == 200:
            print(f"✅ Refund recorded: {refund_id}")
        else:
            print(f"❌ Failed to record refund: {response.text}")

def parse_payment_metadata(note: str) -> dict:
    """Parse payment metadata from Square note field"""

    # Expected format: "subscription_id:XXX,company_name:YYY"
    try:
        return dict(item.split(":") for item in note.split(","))
    except:
        return {}
```

---

## Error Handling Scenarios

### Scenario 11: Handling API Errors Gracefully

**Goal:** Implement robust error handling for payment operations

```python
import logging
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaymentAPIError(Exception):
    """Base exception for payment API errors"""
    pass

class PaymentNotFoundError(PaymentAPIError):
    """Payment not found"""
    pass

class InvalidRefundError(PaymentAPIError):
    """Invalid refund request"""
    pass

class PaymentAPIClient:
    """Robust payment API client with error handling"""

    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }

    def get_payment(self, square_payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment with error handling"""

        try:
            response = requests.get(
                f"{self.base_url}/api/v1/payments/square/{square_payment_id}"
            )

            if response.status_code == 404:
                logger.error(f"Payment not found: {square_payment_id}")
                raise PaymentNotFoundError(f"Payment not found: {square_payment_id}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to payment API")
            return None
        except requests.exceptions.Timeout:
            logger.error("Payment API request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return None

    def process_refund_safe(
        self,
        square_payment_id: str,
        refund_amount: int
    ) -> Optional[Dict[str, Any]]:
        """Process refund with comprehensive error handling"""

        try:
            # Get payment first
            payment = self.get_payment(square_payment_id)

            if not payment:
                raise PaymentNotFoundError(f"Payment not found: {square_payment_id}")

            # Validate refund amount
            payment_amount = payment["amount"]
            existing_refunds = payment.get("refunds", [])
            total_refunded = sum(r["amount"] for r in existing_refunds)
            remaining = payment_amount - total_refunded

            if refund_amount > remaining:
                raise InvalidRefundError(
                    f"Refund amount ({refund_amount}) exceeds remaining ({remaining})"
                )

            if refund_amount <= 0:
                raise InvalidRefundError("Refund amount must be positive")

            # Process refund
            import uuid
            refund_data = {
                "refund_id": f"rfn_{uuid.uuid4().hex[:12]}",
                "amount": refund_amount,
                "currency": "USD",
                "idempotency_key": f"rfd_{uuid.uuid4()}"
            }

            response = requests.post(
                f"{self.base_url}/api/v1/payments/{square_payment_id}/refund",
                headers=self.headers,
                json=refund_data,
                timeout=30
            )

            if response.status_code == 400:
                error_detail = response.json().get("detail", "Unknown error")
                logger.error(f"Refund validation failed: {error_detail}")
                raise InvalidRefundError(error_detail)

            response.raise_for_status()
            logger.info(f"✅ Refund processed successfully: {refund_amount / 100:.2f} USD")
            return response.json()

        except PaymentNotFoundError:
            logger.error(f"Cannot process refund - payment not found: {square_payment_id}")
            raise
        except InvalidRefundError:
            logger.error(f"Cannot process refund - invalid request")
            raise
        except requests.exceptions.Timeout:
            logger.error("Refund request timed out")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing refund: {e}", exc_info=True)
            return None

# Usage with error handling
client = PaymentAPIClient(
    base_url="http://localhost:8000",
    admin_token="your_admin_token"
)

try:
    result = client.process_refund_safe(
        square_payment_id="sq_payment_123",
        refund_amount=500
    )

    if result:
        print("Refund successful!")
    else:
        print("Refund failed - check logs")

except PaymentNotFoundError as e:
    print(f"Error: {e}")
    # Handle: Maybe payment was deleted, notify admin

except InvalidRefundError as e:
    print(f"Error: {e}")
    # Handle: Show error to user, request different amount
```

---

**End of Scenarios**
