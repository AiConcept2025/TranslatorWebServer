# Manual Testing Guide - Stripe Payment Links

## Overview

This guide provides step-by-step instructions for manually testing Stripe Payment Links for invoices, including webhook payment processing.

---

## ✅ CRITICAL BUG FIXED

**Issue:** Webhook handler was creating DUPLICATE invoices instead of updating existing ones.

**Previous Behavior (BEFORE FIX):**
1. Send invoice email → Creates invoice with status "sent" + payment link
2. User pays → Webhook receives payment → Created NEW invoice with status "paid"
3. Result: TWO invoices (one "sent", one "paid")

**Current Behavior (AFTER FIX):**
1. Send invoice email → Creates invoice with status "sent" + payment link (metadata includes `invoice_id`)
2. User pays → Webhook receives payment → **UPDATES existing invoice** to status "paid"
3. Result: **ONE invoice** (status changes from "sent" to "paid") ✅

**What Was Fixed:**
- `app/services/webhook_handler.py` lines 272-404
- Now extracts `invoice_id` from `payment_intent.metadata`
- Updates existing invoice instead of creating duplicate
- Sets `status="paid"`, `stripe_payment_intent_id`, `amount_paid`, `paid_at`
- Maintains backward compatibility for legacy payments without invoice metadata

**Tests:**
- `tests/integration/test_invoice_payment_link_webhook.py` - 4 comprehensive tests
- Verifies no duplicate invoices created
- Verifies invoice status update
- Verifies idempotency
- Verifies graceful error handling

---

## Prerequisites

### 1. Environment Setup

```bash
# Server must be running with .env configuration
cd /Users/vladimirdanishevsky/projects/Translator/server
source .venv/bin/python
uvicorn app.main:app --reload --port 8000
```

### 2. Stripe Test Mode

**Verify Stripe test keys in `.env`:**
```bash
STRIPE_SECRET_KEY=sk_test_...  # Must be test key
STRIPE_WEBHOOK_SECRET=whsec_...
```

**Access Stripe Dashboard:**
- URL: https://dashboard.stripe.com/test/dashboard
- Switch to "Test mode" (toggle in left sidebar)

### 3. Database Access

```bash
# Connect to MongoDB
mongosh mongodb://localhost:27017/translation

# Verify invoices collection exists
use translation
db.invoices.countDocuments()
```

### 4. Email Configuration

**Verify SMTP settings in `.env`:**
```bash
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-app-password  # Yahoo app-specific password
SMTP_FROM_EMAIL=your-email@yahoo.com
```

---

## Part 1: Manual Testing - Payment Link Creation & Email

### Step 1: Verify Existing Invoice

```bash
# 1. Connect to MongoDB
mongosh mongodb://localhost:27017/translation

# 2. Find an invoice to test with
use translation
db.invoices.findOne({status: "sent"})
# Copy the _id value (e.g., "675c4a3b2e8f1a2b3c4d5e6f")

# 3. Verify invoice has required fields
db.invoices.findOne(
  {_id: ObjectId("675c4a3b2e8f1a2b3c4d5e6f")},
  {invoice_number: 1, total_amount: 1, status: 1, company_name: 1}
)

# Example output:
# {
#   "_id": ObjectId("675c4a3b2e8f1a2b3c4d5e6f"),
#   "invoice_number": "INV-2025-001",
#   "total_amount": Decimal128("100.00"),
#   "status": "sent",
#   "company_name": "Acme Health LLC"
# }
```

**Expected:** Invoice exists with status "sent", has `total_amount` > 0

---

### Step 2: Send Invoice Email with Payment Link

```bash
# Use curl or Postman to send invoice email
curl -X POST http://localhost:8000/api/invoices/675c4a3b2e8f1a2b3c4d5e6f/send-email \
  -H "Content-Type: application/json"

# Expected response:
# {
#   "success": true,
#   "message": "Invoice sent to customer@example.com",
#   "invoice_id": "675c4a3b2e8f1a2b3c4d5e6f",
#   "payment_link_url": "https://buy.stripe.com/test_xxxxxxxx"
# }
```

**Verification Steps:**

1. **Check server logs** (`server_logs.txt` or terminal output):
```
[PAYMENT_LINK] Processing invoice INV-2025-001 (status: sent)
[PAYMENT_LINK] Creating payment link for invoice INV-2025-001: $100.00 (10000 cents)
[PAYMENT_LINK] Created Stripe Price: price_xxxxx for invoice INV-2025-001
[PAYMENT_LINK] Created Stripe Payment Link: plink_xxxxx → https://buy.stripe.com/test_xxxxx
[PAYMENT_LINK] Updated invoice INV-2025-001 with payment link metadata
```

2. **Verify database update:**
```bash
mongosh mongodb://localhost:27017/translation
use translation
db.invoices.findOne(
  {_id: ObjectId("675c4a3b2e8f1a2b3c4d5e6f")},
  {stripe_payment_link_url: 1, stripe_payment_link_id: 1, payment_link_created_at: 1}
)

# Expected output:
# {
#   "_id": ObjectId("675c4a3b2e8f1a2b3c4d5e6f"),
#   "stripe_payment_link_url": "https://buy.stripe.com/test_xxxxxxxx",
#   "stripe_payment_link_id": "plink_xxxxxxxx",
#   "payment_link_created_at": "2025-12-14T10:30:00Z"
# }
```

3. **Check received email:**
   - Look for email in inbox (company contact email)
   - Verify email contains "💳 Pay Invoice Now" button
   - Verify button links to Stripe payment page
   - Verify PDF attachment contains payment link URL

4. **Verify PDF content:**
   - Open PDF attachment
   - Check "Payment Instructions" section exists
   - Verify payment link URL is clickable
   - Text should say "Pay Online: [clickable link]"

---

### Step 3: Test Idempotency (Optional)

```bash
# Send email again for same invoice
curl -X POST http://localhost:8000/api/invoices/675c4a3b2e8f1a2b3c4d5e6f/send-email \
  -H "Content-Type: application/json"

# Expected: Returns SAME payment link URL (not a new one)
```

**Verification:**
- Server logs should show: `[PAYMENT_LINK] Invoice INV-2025-001 already has payment link: https://buy.stripe.com/test_xxxxx`
- Response should have same `payment_link_url` as first call
- Stripe dashboard should NOT show duplicate Payment Links for same invoice

---

## Part 2: Manual Testing - Payment via Stripe

### Step 4: Complete Payment on Stripe Hosted Page

1. **Open payment link** (from email or API response):
   - Click "Pay Invoice Now" button in email, OR
   - Copy `payment_link_url` from API response and open in browser

2. **Verify Stripe payment page:**
   - Page shows invoice number (e.g., "Invoice INV-2025-001")
   - Amount matches invoice total (e.g., "$100.00 USD")
   - "Powered by Stripe" branding visible

3. **Enter test payment details:**
   ```
   Card Number: 4242 4242 4242 4242  (Stripe test card - always succeeds)
   Expiration: Any future date (e.g., 12/30)
   CVC: Any 3 digits (e.g., 123)
   Email: test-payment@example.com
   Name: Test Customer
   ```

4. **Click "Pay" button**

5. **Expected result:**
   - Success page: "Payment successful"
   - Confirmation message displayed
   - Email sent to payment email address (test-payment@example.com)

---

### Step 5: Verify Stripe Dashboard (Test Mode)

1. **Go to Stripe Dashboard:**
   - URL: https://dashboard.stripe.com/test/payments
   - Ensure "Test mode" is ON

2. **Find payment:**
   - Should see payment for invoice amount
   - Status: "Succeeded"
   - Description: "Invoice INV-2025-001"
   - Payment method: Card ending in 4242

3. **Check Payment Intent details:**
   - Click on payment to see details
   - Verify `metadata` section contains:
     ```json
     {
       "invoice_id": "675c4a3b2e8f1a2b3c4d5e6f",
       "invoice_number": "INV-2025-001"
     }
     ```

4. **Check Payment Link:**
   - Go to https://dashboard.stripe.com/test/payment-links
   - Find payment link for invoice
   - Status should show number of payments (e.g., "1 payment")

---

## Part 3: Webhook Testing (CRITICAL - CURRENTLY BROKEN)

### Step 6: Setup Stripe CLI for Webhook Testing

**IMPORTANT:** This step tests the webhook that updates invoice status to "paid" after payment.

```bash
# Install Stripe CLI (if not installed)
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# Expected output:
# Ready! Your webhook signing secret is whsec_xxxxx (^C to quit)
# Copy the webhook secret
```

**Update `.env` with webhook secret:**
```bash
# Add to .env
STRIPE_WEBHOOK_SECRET=whsec_xxxxx  # From stripe listen command
```

**Restart server:**
```bash
# Terminal 1: Restart uvicorn to load new webhook secret
# Ctrl+C to stop, then:
uvicorn app.main:app --reload --port 8000

# Terminal 2: Keep stripe listen running
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```

---

### Step 7: Trigger Test Webhook

**Option A: Replay Real Payment (Recommended)**

```bash
# In Stripe Dashboard:
# 1. Go to https://dashboard.stripe.com/test/events
# 2. Find the payment_intent.succeeded event for your test payment
# 3. Click event ID (e.g., evt_xxxxx)
# 4. Click "Send test webhook" button
# 5. Select endpoint: localhost:8000/api/webhooks/stripe
# 6. Click "Send test webhook"
```

**Option B: Trigger with Stripe CLI**

```bash
# Trigger test webhook with sample data
stripe trigger payment_intent.succeeded

# NOTE: This creates a NEW payment_intent, not linked to your invoice
# Use Option A for realistic testing
```

---

### Step 8: Verify Webhook Processing (NOW WORKING)

**✅ EXPECTED BEHAVIOR:**

1. **Server logs should show:**
```
[WEBHOOK] Processing event evt_xxxxx type=payment_intent.succeeded payment_intent=pi_xxxxx
[WEBHOOK_SECURITY] Valid signature verified
[WEBHOOK] Event evt_xxxxx stored in webhook_events
[WEBHOOK] Payment created: 675c4a3b2e8f1a2b3c4d5e70
[WEBHOOK] Found existing invoice 675c4a3b2e8f1a2b3c4d5e6f from payment metadata
[WEBHOOK] Updating invoice INV-2025-001 status: sent → paid
[PAYMENT_APP] Applying payment pi_xxxxx to invoice 675c4a3b2e8f1a2b3c4d5e6f
[PAYMENT_APP] Invoice amount_paid updated: $0.00 → $100.00
[PAYMENT_APP] Invoice status updated: sent → paid
[WEBHOOK] Event evt_xxxxx processed successfully
```

2. **Database verification:**
```bash
mongosh mongodb://localhost:27017/translation
use translation

# Verify invoice status changed to "paid"
db.invoices.findOne(
  {_id: ObjectId("675c4a3b2e8f1a2b3c4d5e6f")},
  {status: 1, amount_paid: 1, stripe_payment_intent_id: 1, paid_at: 1}
)

# Expected output:
# {
#   "_id": ObjectId("675c4a3b2e8f1a2b3c4d5e6f"),
#   "status": "paid",  # ✅ Changed from "sent"
#   "amount_paid": Decimal128("100.00"),  # ✅ Updated
#   "stripe_payment_intent_id": "pi_xxxxx",  # ✅ Added
#   "paid_at": ISODate("2025-12-14T10:35:00Z")  # ✅ Added
# }

# Verify payment record created
db.payments.findOne(
  {stripe_payment_intent_id: "pi_xxxxx"},
  {amount: 1, status: 1, invoice_id: 1}
)

# Expected output:
# {
#   "_id": ObjectId("675c4a3b2e8f1a2b3c4d5e70"),
#   "stripe_payment_intent_id": "pi_xxxxx",
#   "amount": Decimal128("100.00"),
#   "status": "succeeded",
#   "invoice_id": "675c4a3b2e8f1a2b3c4d5e6f"  # ✅ Linked to invoice
# }

# Verify NO duplicate invoice created
db.invoices.countDocuments({invoice_number: "INV-2025-001"})
# Expected: 1 (not 2!)
```

**✅ CORRECT BEHAVIOR (After Fix):**

The webhook now correctly updates the existing invoice. No duplicate invoices are created.

---

## Part 4: Subscription Verification

### Step 9: Verify Subscription (If Applicable)

**Note:** Subscriptions are updated independently of invoice payments. Invoice status "paid" is sufficient to track payment. No additional subscription marking is required.

**Optional verification:**
```bash
mongosh mongodb://localhost:27017/translation
use translation

# Find subscription linked to invoice
db.invoices.findOne(
  {_id: ObjectId("675c4a3b2e8f1a2b3c4d5e6f")},
  {subscription_id: 1}
)
# Output: { "subscription_id": "sub_xxxxx" }

# Check subscription status (unchanged by payment)
db.subscriptions.findOne(
  {_id: ObjectId("sub_xxxxx")},
  {status: 1, units_allocated: 1, units_used: 1}
)

# Expected: Subscription status unchanged (payment tracked via invoice.status)
```

---

## Testing Checklist

### Pre-Payment Testing
- [ ] Invoice email sends successfully
- [ ] Email contains "Pay Invoice Now" button
- [ ] Button links to Stripe hosted payment page
- [ ] PDF attachment includes payment link URL
- [ ] Stripe payment page shows correct invoice number and amount
- [ ] Payment link stored in database (`stripe_payment_link_url`, `stripe_payment_link_id`)
- [ ] Idempotency: Re-sending email returns same payment link

### Payment Testing
- [ ] Stripe test card payment succeeds
- [ ] Stripe Dashboard shows payment with correct amount
- [ ] Payment metadata includes `invoice_id` and `invoice_number`
- [ ] Payment Link shows payment count

### Webhook Testing (WORKING)
- [ ] Stripe CLI webhook forwarding works
- [ ] Webhook signature verification passes
- [ ] ✅ Invoice status changes from "sent" to "paid"
- [ ] ✅ Invoice `amount_paid` updated to match total
- [ ] ✅ Invoice `stripe_payment_intent_id` set
- [ ] ✅ Invoice `paid_at` timestamp set
- [ ] ✅ NO duplicate invoice created
- [ ] Payment record created with `invoice_id` link
- [ ] Webhook event stored in `webhook_events` collection

### Database Verification
- [ ] Only ONE invoice exists for invoice number
- [ ] Invoice status = "paid" (not "sent")
- [ ] Invoice `amount_paid` = total_amount
- [ ] Payment record linked to invoice via `invoice_id`
- [ ] No orphaned payments or duplicate invoices

---

## Troubleshooting

### Issue: Email Not Received

**Diagnosis:**
```bash
# Check server logs for SMTP errors
grep "SMTP" server_logs.txt

# Test SMTP connection
python3 << EOF
import smtplib
server = smtplib.SMTP('smtp.mail.yahoo.com', 587)
server.starttls()
server.login('your-email@yahoo.com', 'your-app-password')
print("SMTP connection successful")
server.quit()
EOF
```

**Common Causes:**
- Yahoo app password incorrect
- Yahoo account 2FA not enabled
- SMTP rate limiting (wait 5 minutes)

---

### Issue: Payment Link Not Created

**Diagnosis:**
```bash
# Check server logs for Stripe API errors
grep "PAYMENT_LINK" server_logs.txt | grep "error"

# Verify Stripe API key
curl https://api.stripe.com/v1/balance \
  -u sk_test_your_key:
```

**Common Causes:**
- Invalid Stripe API key in `.env`
- Invoice already paid (status != "sent")
- Invoice total_amount is None or 0

---

### Issue: Webhook Not Triggered

**Diagnosis:**
```bash
# Check if Stripe CLI is running
ps aux | grep "stripe listen"

# Verify webhook secret in .env matches stripe listen output
grep STRIPE_WEBHOOK_SECRET .env

# Check webhook endpoint logs
grep "WEBHOOK" server_logs.txt
```

**Common Causes:**
- Stripe CLI not running (`stripe listen`)
- Wrong webhook secret in `.env`
- Server not running on port 8000
- Firewall blocking webhook delivery

---

### Issue: Duplicate Invoices Created

**This issue has been FIXED.**

**Diagnosis (if you suspect duplicates):**
```bash
# Check for duplicate invoices
mongosh mongodb://localhost:27017/translation
use translation
db.invoices.aggregate([
  {$group: {_id: "$invoice_number", count: {$sum: 1}}},
  {$match: {count: {$gt: 1}}}
])
```

**If you still see duplicates after fix:**
This shouldn't happen with the new code. If it does:
1. Check server logs for errors
2. Verify webhook handler code is updated
3. Ensure server was restarted after code changes
4. Report the issue with logs

---

## Implementation Summary

### Bug Fix Completed ✅

**File:** `app/services/webhook_handler.py`
**Lines:** 272-404
**Function:** `_handle_payment_succeeded()`

**What Was Changed:**

1. **Extract invoice metadata** (lines 272-280):
   - Extracts `invoice_id` and `invoice_number` from `payment_intent.metadata`
   - Logs when payment is linked to existing invoice

2. **Conditional invoice handling** (lines 330-404):
   - **IF** invoice_id in metadata → **UPDATE** existing invoice
   - **ELSE** → **CREATE** new invoice (backward compatibility)

3. **Invoice update logic** (lines 345-356):
   - Uses `find_one_and_update()` with ObjectId lookup
   - Sets `status="paid"`, `stripe_payment_intent_id`, `amount_paid`, `paid_at`
   - Converts amount to Decimal128 for MongoDB

4. **Error handling** (lines 365-379):
   - Handles missing invoice gracefully (logs warning)
   - Doesn't crash webhook processing if update fails
   - Payment record still created for manual reconciliation

### Integration Tests Created ✅

**File:** `tests/integration/test_invoice_payment_link_webhook.py`

**4 comprehensive tests:**

1. `test_payment_link_webhook_updates_existing_invoice()`
   - Verifies invoice updated (not duplicated)
   - Verifies status change: "sent" → "paid"
   - Verifies payment fields set correctly

2. `test_payment_link_webhook_handles_missing_invoice_gracefully()`
   - Tests error handling for invalid invoice_id
   - Verifies webhook doesn't crash
   - Verifies payment still created

3. `test_legacy_payment_without_invoice_metadata_creates_invoice()`
   - Tests backward compatibility
   - Verifies new invoice created for legacy payments
   - Ensures old payment flows still work

4. `test_payment_link_webhook_idempotency()`
   - Tests duplicate webhook handling
   - Verifies invoice not updated twice
   - Verifies timestamp unchanged on retry

---

## Summary

### What Works ✅
- ✅ Payment link creation
- ✅ Email sending with payment button
- ✅ PDF generation with payment link
- ✅ Stripe payment page
- ✅ Test payment processing
- ✅ Webhook signature verification
- ✅ Payment record creation
- ✅ **Webhook invoice update** (FIXED - updates existing invoice)
- ✅ **Invoice status change** (FIXED - changes "sent" to "paid")
- ✅ **No duplicate invoices** (FIXED - only one invoice created)

### Testing Required
1. ✅ Run integration tests: `pytest tests/integration/test_invoice_payment_link_webhook.py -v`
2. ⏳ Manual end-to-end test following this guide
3. ⏳ Verify in staging environment
4. ⏳ Deploy to production with monitoring

---

## Production Deployment Checklist

Before deploying to production:
- [ ] Bug fix implemented and tested
- [ ] Integration tests passing
- [ ] Manual test completed successfully (all checkboxes above)
- [ ] Stripe production webhook endpoint configured
- [ ] Stripe production webhook secret in production `.env`
- [ ] Email SMTP credentials for production
- [ ] Database backup taken
- [ ] Monitoring alerts configured for webhook failures
- [ ] Rollback plan documented
