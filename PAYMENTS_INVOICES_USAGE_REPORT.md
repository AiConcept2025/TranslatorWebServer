# Payments and Invoices Collections Usage Report

**Date:** December 1, 2025
**Post-Migration Status:** Square → Stripe Migration Complete
**Purpose:** Document how `payments` and `invoices` collections are used in the backend

---

## Executive Summary

The backend uses **two separate collections** for tracking subscription billing:

1. **`payments`** - Records actual payment transactions from Stripe
2. **`invoices`** - Tracks billing documents and their status

**Key Finding:** Both collections are **manually managed** via admin endpoints. There is **NO automated invoice generation or payment recording** currently implemented.

---

## 1. Payments Collection

### 1.1 Collection Purpose
The `payments` collection tracks **subscription payment records** for enterprise customers. Each document represents a payment made through Stripe for a subscription service.

### 1.2 Schema Structure
```typescript
{
  _id: ObjectId,
  stripe_payment_intent_id: string,      // Stripe payment ID
  stripe_invoice_id?: string,            // Stripe order/invoice ID
  stripe_customer_id?: string,           // Stripe customer ID
  company_name: string,                  // Company making payment
  subscription_id?: string,              // Related subscription ObjectId
  user_id?: string,                      // User who made payment
  user_email: string,                    // Email of payer
  amount: number,                        // Amount in cents
  currency: string,                      // Currency code (default: "USD")
  payment_status: string,                // COMPLETED | PENDING | FAILED | REFUNDED
  payment_date: Date,                    // When payment was processed
  payment_method?: string,               // Payment method (e.g., "card")
  card_brand?: string,                   // Card brand (VISA, MASTERCARD, etc.)
  card_last_4?: string,                  // Last 4 digits of card
  receipt_url?: string,                  // URL to Stripe receipt
  refunds: Array<{                       // Array of refund records
    refund_id: string,
    amount: number,
    currency: string,
    status: string,
    idempotency_key: string,
    created_at: Date
  }>,
  created_at: Date,
  updated_at: Date
}
```

### 1.3 Payment Creation Endpoints

#### 1.3.1 Individual Payment Creation (Manual)
**Endpoint:** `POST /api/v1/payments`
**Auth:** None (should be protected)
**File:** `app/routers/payments.py` (Line 464)

**Trigger:** Manual API call from external system
**Code Location:** `app/routers/payments.py:464-583`

```python
@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_data: PaymentCreate):
    """Create a new payment record."""
    # Creates payment in database
    payment_id = await payment_repository.create_payment(payment_data)
    # Inserts into payments collection
```

**Database Operation:**
```python
# File: app/services/payment_repository.py:25-60
async def create_payment(self, payment_data: PaymentCreate) -> str:
    payment_doc = {
        "company_name": payment_data.company_name,
        "user_email": payment_data.user_email,
        "stripe_payment_intent_id": payment_data.stripe_payment_intent_id,
        "amount": payment_data.amount,
        "currency": payment_data.currency,
        "payment_status": payment_data.payment_status,
        "refunds": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "payment_date": payment_data.payment_date or datetime.now(timezone.utc)
    }
    result = await self.collection.insert_one(payment_doc)
    return str(result.inserted_id)
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Health LLC",
    "user_email": "test@example.com",
    "stripe_payment_intent_id": "pi_abc123",
    "amount": 9000,
    "currency": "USD",
    "payment_status": "COMPLETED"
  }'
```

#### 1.3.2 Subscription Payment Creation (Admin Only)
**Endpoint:** `POST /api/v1/payments/subscription`
**Auth:** Admin required
**File:** `app/routers/payments.py` (Line 585)

**Trigger:** Manual admin action to record subscription payment
**Code Location:** `app/routers/payments.py:679-893`

```python
@router.post("/subscription", status_code=status.HTTP_201_CREATED)
async def create_subscription_payment(
    payment_data: SubscriptionPaymentCreate,
    admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Create a subscription payment record (Admin Only)."""
    # Validates subscription exists
    subscription = await database.subscriptions.find_one({"_id": subscription_obj_id})

    # Validates company name matches
    if subscription_company != payment_data.company_name:
        raise HTTPException(status_code=400, detail="Company name mismatch")

    # Creates payment document
    payment_doc = {
        "stripe_payment_intent_id": payment_data.stripe_payment_intent_id,
        "stripe_invoice_id": payment_data.stripe_invoice_id,
        "stripe_customer_id": payment_data.stripe_customer_id,
        "company_name": payment_data.company_name,
        "subscription_id": payment_data.subscription_id,
        "user_id": payment_data.user_id,
        "user_email": payment_data.user_email,
        "amount": payment_data.amount,
        "currency": payment_data.currency,
        "payment_status": payment_data.payment_status,
        "payment_date": payment_data.payment_date or now,
        "payment_method": payment_data.payment_method,
        "card_brand": payment_data.card_brand,
        "card_last_4": payment_data.card_last_4,
        "receipt_url": payment_data.receipt_url,
        "refunds": [],
        "created_at": now,
        "updated_at": now
    }

    # Insert into MongoDB - LINE 847
    result = await database.payments.insert_one(payment_doc)
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "stripe_payment_intent_id": "pi_stripe123",
    "stripe_invoice_id": "in_stripe456",
    "stripe_customer_id": "cus_stripe789",
    "user_email": "admin@acme.com",
    "amount": 9000,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "payment_method": "card",
    "card_brand": "VISA",
    "card_last_4": "1234",
    "receipt_url": "https://stripe.com/receipt/..."
  }'
```

### 1.4 Payment Read/Query Endpoints

#### 1.4.1 Get All Payments (Admin Only)
**Endpoint:** `GET /api/v1/payments`
**Auth:** Admin required
**File:** `app/routers/payments.py:246`

**Purpose:** Admin dashboard to view all payments across all companies

```bash
# Get all payments
curl -X GET "http://localhost:8000/api/v1/payments" \
  -H "Authorization: Bearer {admin_token}"

# Filter by status
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&limit=20"

# Filter by company
curl -X GET "http://localhost:8000/api/v1/payments?company_name=Acme%20Health%20LLC"
```

#### 1.4.2 Get Payment by ID
**Endpoint:** `GET /api/v1/payments/{payment_id}`
**File:** `app/routers/payments.py:896`

```bash
curl -X GET "http://localhost:8000/api/v1/payments/68ec42a48ca6a1781d9fe5c2"
```

#### 1.4.3 Get Payment by Stripe ID
**Endpoint:** `GET /api/v1/payments/square/{stripe_payment_intent_id}`
**File:** `app/routers/payments.py:967`

```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/pi_abc123"
```

#### 1.4.4 Get Company Payments
**Endpoint:** `GET /api/v1/payments/company/{company_name}`
**File:** `app/routers/payments.py:1035`

```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED&limit=20"
```

#### 1.4.5 Get Payments by Email
**Endpoint:** `GET /api/v1/payments/email/{email}`
**File:** `app/routers/payments.py:1375`

```bash
curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com"
```

#### 1.4.6 Get Company Payment Stats
**Endpoint:** `GET /api/v1/payments/company/{company_name}/stats`
**File:** `app/routers/payments.py:1758`

```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01&end_date=2025-12-31"
```

### 1.5 Payment Update Endpoints

#### 1.5.1 Update Payment
**Endpoint:** `PATCH /api/v1/payments/{stripe_payment_intent_id}`
**File:** `app/routers/payments.py:1460`

```bash
curl -X PATCH "http://localhost:8000/api/v1/payments/pi_abc123" \
  -H "Content-Type: application/json" \
  -d '{"payment_status":"COMPLETED"}'
```

#### 1.5.2 Process Refund
**Endpoint:** `POST /api/v1/payments/{stripe_payment_intent_id}/refund`
**File:** `app/routers/payments.py:1569`

```bash
curl -X POST "http://localhost:8000/api/v1/payments/pi_abc123/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_01J2M9ABCD",
    "amount": 500,
    "currency": "USD",
    "idempotency_key": "rfd_unique_key"
  }'
```

### 1.6 Payment Data Flow Summary

```
TRIGGER → ENDPOINT → SERVICE → DATABASE
```

#### Flow 1: Individual Payment Creation
```
External API Call
  ↓
POST /api/v1/payments (payments.py:464)
  ↓
payment_repository.create_payment() (payment_repository.py:25)
  ↓
database.payments.insert_one(payment_doc) (payment_repository.py:59)
  ↓
Payment record created in MongoDB
```

#### Flow 2: Subscription Payment Creation
```
Admin Dashboard Action
  ↓
POST /api/v1/payments/subscription (payments.py:585)
  ↓
Validate subscription exists (payments.py:799)
  ↓
Validate company name matches (payments.py:808)
  ↓
database.payments.insert_one(payment_doc) (payments.py:847)
  ↓
Payment record created in MongoDB
```

---

## 2. Invoices Collection

### 2.1 Collection Purpose
The `invoices` collection tracks **billing documents** for enterprise subscription customers. Each invoice represents a billing period with amounts owed/paid.

### 2.2 Schema Structure
```typescript
{
  _id: ObjectId,
  invoice_id?: string,                   // Legacy field (optional)
  company_name: string,                  // Company being billed
  subscription_id: string,               // Related subscription (ObjectId or string)
  invoice_number: string,                // Unique invoice number (e.g., "INV-2025-001")
  invoice_date: Date,                    // Invoice creation date
  due_date: Date,                        // Payment due date
  total_amount: number,                  // Total amount in dollars
  tax_amount: number,                    // Tax amount in dollars
  status: string,                        // sent | paid | overdue | cancelled
  pdf_url?: string,                      // URL to invoice PDF
  payment_applications: Array<{         // Payments applied to this invoice
    payment_id: string,
    amount: number,
    applied_date: Date
  }>,
  created_at: Date
}
```

### 2.3 Invoice Creation Endpoint

**Endpoint:** `POST /api/v1/invoices`
**Auth:** None (should be protected)
**File:** `app/routers/invoices.py` (Line 437)

**Trigger:** Manual API call (no automation)
**Code Location:** `app/routers/invoices.py:538-724`

```python
@router.post("", response_model=InvoiceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(invoice_data: InvoiceCreate):
    """Create a new invoice."""

    # Validate company exists (Line 622)
    company = await database.company.find_one({"company_name": invoice_data.company_name})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Validate subscription exists (Line 633)
    subscription = await database.subscriptions.find_one(subscription_query)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Check for duplicate invoice number (Line 651)
    existing_invoice = await database.invoices.find_one({"invoice_number": invoice_data.invoice_number})
    if existing_invoice:
        raise HTTPException(status_code=400, detail="Invoice number already exists")

    # Create invoice document (Line 661)
    invoice_doc = {
        "company_name": invoice_data.company_name,
        "subscription_id": invoice_data.subscription_id,
        "invoice_number": invoice_data.invoice_number,
        "invoice_date": datetime.fromisoformat(invoice_data.invoice_date.replace("Z", "+00:00")),
        "due_date": datetime.fromisoformat(invoice_data.due_date.replace("Z", "+00:00")),
        "total_amount": invoice_data.total_amount,
        "tax_amount": invoice_data.tax_amount,
        "status": invoice_data.status,
        "pdf_url": invoice_data.pdf_url,
        "payment_applications": [],
        "created_at": created_at
    }

    # Insert into MongoDB - LINE 678
    result = await database.invoices.insert_one(invoice_doc)
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/invoices" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Health LLC",
    "subscription_id": "sub_abc123",
    "invoice_number": "INV-2025-001",
    "invoice_date": "2025-10-08T00:07:00.396Z",
    "due_date": "2025-11-07T00:07:00.396Z",
    "total_amount": 106.00,
    "tax_amount": 6.00,
    "status": "sent",
    "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf"
  }'
```

### 2.4 Invoice Read/Query Endpoints

#### 2.4.1 Get Company Invoices
**Endpoint:** `GET /api/v1/invoices/company/{company_name}`
**File:** `app/routers/invoices.py:199`

**Purpose:** Retrieve all invoices for a specific company with filtering

```bash
# Get all invoices
curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp"

# Filter by status
curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp?status=sent"

# Pagination
curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp?skip=20&limit=20"
```

**Code Flow:**
```python
# File: app/routers/invoices.py:199-434
async def get_company_invoices(company_name: str, status_filter: Optional[str] = None, ...):
    # Build MongoDB aggregation pipeline
    match_stage = {"company_name": company_name}
    if status_filter:
        match_stage["status"] = status_filter

    pipeline = [
        {"$match": match_stage},
        {"$skip": skip},
        {"$limit": limit}
    ]

    # Execute query - LINE 338
    invoices = await database.invoices.aggregate(pipeline).to_list(length=limit)
```

### 2.5 Invoice Update Endpoint

**Endpoint:** `PATCH /api/v1/invoices/{invoice_id}`
**File:** `app/routers/invoices.py:806`

**Purpose:** Update invoice fields (status, amounts, dates, PDF URL)

```bash
# Update status to paid
curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \
  -H "Content-Type: application/json" \
  -d '{"status": "paid"}'

# Update PDF URL
curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \
  -H "Content-Type: application/json" \
  -d '{"pdf_url": "https://storage.example.com/invoices/INV-2025-001-updated.pdf"}'

# Update multiple fields
curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "paid",
    "total_amount": 110.00,
    "tax_amount": 10.00
  }'
```

**Code Location:** `app/routers/invoices.py:806-1002`

```python
async def update_invoice(invoice_id: str, update_data: InvoiceUpdate):
    # Validate ObjectId (Line 881)
    obj_id = ObjectId(invoice_id)

    # Check invoice exists (Line 891)
    existing_invoice = await database.invoices.find_one({"_id": obj_id})

    # Get fields to update (Line 877)
    update_dict = update_data.model_dump(exclude_unset=True)

    # Update in database - LINE 943
    result = await database.invoices.update_one(
        {"_id": obj_id},
        {"$set": update_dict}
    )
```

### 2.6 Invoice Data Flow Summary

```
TRIGGER → ENDPOINT → VALIDATION → DATABASE
```

#### Flow 1: Invoice Creation
```
Manual API Call (Admin or External System)
  ↓
POST /api/v1/invoices (invoices.py:538)
  ↓
Validate company exists (invoices.py:622)
  ↓
Validate subscription exists (invoices.py:633)
  ↓
Check duplicate invoice_number (invoices.py:651)
  ↓
database.invoices.insert_one(invoice_doc) (invoices.py:678)
  ↓
Invoice record created in MongoDB
```

#### Flow 2: Invoice Query
```
Frontend/API Request
  ↓
GET /api/v1/invoices/company/{company_name} (invoices.py:199)
  ↓
Build aggregation pipeline (invoices.py:315-330)
  ↓
database.invoices.aggregate(pipeline) (invoices.py:338)
  ↓
Return filtered/paginated invoices
```

#### Flow 3: Invoice Update
```
Manual API Call
  ↓
PATCH /api/v1/invoices/{invoice_id} (invoices.py:806)
  ↓
Validate invoice exists (invoices.py:891)
  ↓
database.invoices.update_one() (invoices.py:943)
  ↓
Invoice updated in MongoDB
```

---

## 3. Relationship Between Collections

### 3.1 Conceptual Relationship

```
Subscriptions (active billing agreement)
     │
     ├─→ Invoices (billing documents)
     │      └─→ Shows what is owed/due
     │
     └─→ Payments (actual money received)
            └─→ Records payment transactions
```

### 3.2 Data Linkage

**Invoice → Subscription:**
```javascript
{
  invoice_id: "inv_123",
  subscription_id: "sub_abc123",  // Links to subscription
  company_name: "Acme Corp",
  total_amount: 100.00,
  status: "sent"
}
```

**Payment → Subscription:**
```javascript
{
  payment_id: "pay_456",
  subscription_id: "sub_abc123",  // Links to subscription
  company_name: "Acme Corp",
  amount: 10000,  // In cents
  payment_status: "COMPLETED"
}
```

### 3.3 Current Limitations

**⚠️ NO Automatic Linkage:**
- Invoices and payments are **NOT automatically linked** to each other
- `payment_applications` array in invoices is **NOT populated automatically**
- Admin must manually track which payments apply to which invoices

**⚠️ NO Automated Processes:**
- No automatic invoice generation on subscription renewal
- No automatic payment recording from Stripe webhooks
- No automatic invoice status updates when payments are received

---

## 4. Missing Automation (Opportunities)

### 4.1 What's NOT Implemented

#### 4.1.1 Automatic Invoice Generation
**Current State:** Invoices must be created manually via `POST /api/v1/invoices`

**Needed:**
```python
# NOT IMPLEMENTED
async def generate_monthly_invoices():
    """Run monthly to create invoices for all active subscriptions."""
    active_subscriptions = await database.subscriptions.find({"status": "active"})

    for subscription in active_subscriptions:
        # Calculate billing period
        # Generate invoice number
        # Create invoice document
        # Send invoice to customer
        pass
```

#### 4.1.2 Stripe Webhook Handler
**Current State:** No webhook handler for Stripe events

**Needed:**
```python
# NOT IMPLEMENTED
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    event = stripe.Webhook.construct_event(...)

    if event.type == "payment_intent.succeeded":
        # Automatically create payment record
        await create_payment_from_stripe(event.data.object)

    elif event.type == "invoice.paid":
        # Update invoice status to "paid"
        await update_invoice_status(event.data.object.id, "paid")

    return {"received": True}
```

#### 4.1.3 Payment → Invoice Application
**Current State:** `payment_applications` array is always empty

**Needed:**
```python
# NOT IMPLEMENTED
async def apply_payment_to_invoice(payment_id: str, invoice_id: str, amount: float):
    """Link a payment to an invoice."""
    await database.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$push": {
            "payment_applications": {
                "payment_id": payment_id,
                "amount": amount,
                "applied_date": datetime.now(timezone.utc)
            }
        }}
    )

    # Update invoice status if fully paid
    invoice = await database.invoices.find_one({"_id": ObjectId(invoice_id)})
    total_applied = sum(app["amount"] for app in invoice["payment_applications"])
    if total_applied >= invoice["total_amount"]:
        await database.invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": {"status": "paid"}}
        )
```

#### 4.1.4 Scheduled Tasks
**Current State:** No cron jobs or scheduled tasks

**Needed:**
```python
# NOT IMPLEMENTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day=1)  # Run on 1st of every month
async def monthly_invoice_generation():
    """Generate invoices for all active subscriptions."""
    await generate_monthly_invoices()

@scheduler.scheduled_job('cron', hour=0)  # Run daily at midnight
async def check_overdue_invoices():
    """Mark invoices as overdue if past due_date."""
    await database.invoices.update_many(
        {"due_date": {"$lt": datetime.now(timezone.utc)}, "status": "sent"},
        {"$set": {"status": "overdue"}}
    )
```

### 4.2 Recommended Implementation Priority

**Phase 1: Critical**
1. Stripe webhook handler for `payment_intent.succeeded`
2. Automatic payment record creation from webhooks

**Phase 2: Important**
3. Monthly invoice generation for active subscriptions
4. Payment → Invoice application logic

**Phase 3: Enhancement**
5. Automated overdue invoice marking
6. Automated email notifications for invoices

---

## 5. Code Reference Index

### 5.1 Payments Collection

| Operation | Endpoint | File | Line | Function |
|-----------|----------|------|------|----------|
| **CREATE** | `POST /api/v1/payments` | `app/routers/payments.py` | 464 | `create_payment()` |
| **CREATE** | `POST /api/v1/payments/subscription` | `app/routers/payments.py` | 585 | `create_subscription_payment()` |
| **READ** | `GET /api/v1/payments` | `app/routers/payments.py` | 246 | `get_all_payments()` |
| **READ** | `GET /api/v1/payments/{payment_id}` | `app/routers/payments.py` | 896 | `get_payment_by_id()` |
| **READ** | `GET /api/v1/payments/square/{stripe_id}` | `app/routers/payments.py` | 967 | `get_payment_by_square_id()` |
| **READ** | `GET /api/v1/payments/company/{name}` | `app/routers/payments.py` | 1035 | `get_company_payments()` |
| **READ** | `GET /api/v1/payments/email/{email}` | `app/routers/payments.py` | 1375 | `get_payments_by_email()` |
| **READ** | `GET /api/v1/payments/company/{name}/stats` | `app/routers/payments.py` | 1758 | `get_company_payment_stats()` |
| **UPDATE** | `PATCH /api/v1/payments/{stripe_id}` | `app/routers/payments.py` | 1460 | `update_payment()` |
| **UPDATE** | `POST /api/v1/payments/{stripe_id}/refund` | `app/routers/payments.py` | 1569 | `process_refund()` |

**Database Insert Locations:**
- `payment_repository.py:59` - `await self.collection.insert_one(payment_doc)`
- `payments.py:847` - `await database.payments.insert_one(payment_doc)`

### 5.2 Invoices Collection

| Operation | Endpoint | File | Line | Function |
|-----------|----------|------|------|----------|
| **CREATE** | `POST /api/v1/invoices` | `app/routers/invoices.py` | 437 | `create_invoice()` |
| **READ** | `GET /api/v1/invoices/company/{name}` | `app/routers/invoices.py` | 199 | `get_company_invoices()` |
| **UPDATE** | `PATCH /api/v1/invoices/{invoice_id}` | `app/routers/invoices.py` | 806 | `update_invoice()` |

**Database Insert Locations:**
- `invoices.py:678` - `await database.invoices.insert_one(invoice_doc)`

**Database Update Locations:**
- `invoices.py:943` - `await database.invoices.update_one({...})`

### 5.3 Models

| Model | File | Line | Purpose |
|-------|------|------|---------|
| `Payment` | `app/models/payment.py` | 38 | Full payment document schema |
| `PaymentCreate` | `app/models/payment.py` | 69 | Create payment request schema |
| `SubscriptionPaymentCreate` | `app/models/payment.py` | 135 | Create subscription payment (admin) |
| `InvoiceListItem` | `app/models/invoice.py` | 14 | Invoice response schema |
| `InvoiceCreate` | `app/models/invoice.py` | 224 | Create invoice request schema |
| `InvoiceUpdate` | `app/models/invoice.py` | 257 | Update invoice request schema |

---

## 6. Integration Workflows (Current)

### 6.1 Monthly Subscription Billing (Manual)

**Current Process:**
1. **Admin manually creates invoice** via `POST /api/v1/invoices`
2. **Customer receives invoice** (external email system)
3. **Customer makes payment** through Stripe
4. **Admin manually records payment** via `POST /api/v1/payments/subscription`
5. **Admin manually updates invoice** status via `PATCH /api/v1/invoices/{id}`

**All steps require manual intervention**

### 6.2 Payment Refund Process

**Current Process:**
1. Admin processes refund in Stripe dashboard
2. Admin records refund via `POST /api/v1/payments/{id}/refund`
3. System updates payment record with refund details

### 6.3 Company Dashboard View

**Current Process:**
1. Frontend calls `GET /api/v1/invoices/company/{name}` - gets all invoices
2. Frontend calls `GET /api/v1/payments/company/{name}` - gets all payments
3. Frontend manually correlates invoices with payments (if needed)

**No automatic linkage between collections**

---

## 7. Conclusion

### 7.1 Summary

Both `payments` and `invoices` collections are **fully manual**:
- ✅ **CRUD endpoints exist** for both collections
- ✅ **Data validation** is implemented (company/subscription checks)
- ❌ **NO automated invoice generation** on subscription renewal
- ❌ **NO webhook handlers** for Stripe events
- ❌ **NO automatic payment recording** from Stripe
- ❌ **NO automatic invoice status updates** when paid
- ❌ **NO scheduled tasks** for billing operations

### 7.2 Current Usage Pattern

**Payments Collection:**
- Created via API calls when payment is received
- Queried for company payment history and stats
- Updated for refunds

**Invoices Collection:**
- Created manually via API when billing period starts
- Queried for company billing history
- Updated manually when payment is received

### 7.3 Next Steps

**To make this production-ready, you need:**
1. Implement Stripe webhook handler
2. Add automated invoice generation (monthly cron job)
3. Add payment → invoice application logic
4. Add automated invoice status updates
5. Add email notifications for invoices

**Files to create:**
- `app/routers/webhooks.py` - Stripe webhook handler
- `app/services/invoice_generator.py` - Monthly invoice generation
- `app/services/scheduler_service.py` - Cron jobs for billing tasks
- `app/services/payment_applicator.py` - Link payments to invoices

---

**Document Version:** 1.0
**Last Updated:** December 1, 2025
**Author:** Claude (Anthropic)
