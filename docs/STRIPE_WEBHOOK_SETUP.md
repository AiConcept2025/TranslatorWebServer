# Stripe Webhook Integration - Setup & Testing Guide

> **Complete guide for configuring and testing production-ready Stripe webhook integration**
>
> **Implementation Date**: December 2025
> **Status**: Production-ready with TDD test coverage (45 tests)

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Stripe Dashboard Configuration](#stripe-dashboard-configuration)
5. [Local Development Testing](#local-development-testing)
6. [Testing Checklist](#testing-checklist)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### What This System Does

The Stripe webhook integration provides **production-reliable payment processing** with automatic failover:

```
PRIMARY PATH (Webhook):
Stripe → POST /api/webhooks/stripe (HMAC-verified)
  → Store event in webhook_events (unique event_id)
  → Process payment in background
  → Return 200 immediately (<100ms)

FALLBACK PATH (Client Notification):
Browser → POST /api/payment/success
  → Check if webhook already processed (webhook_processing flag)
  → If yes: Skip processing, return "Already processed"
  → If no: Process payment (webhook didn't arrive)
```

### Architecture Benefits

- ✅ **Reliability**: Payments process even if user loses connection
- ✅ **Idempotency**: No duplicate processing (event-level + payment-level)
- ✅ **Security**: HMAC-SHA256 signature verification prevents spoofing
- ✅ **Audit Trail**: 90-day webhook event retention in MongoDB
- ✅ **Performance**: Background processing, fast responses

---

## Prerequisites

### Required Tools

1. **Stripe Account** (Test mode or Live mode)
   - Sign up at https://stripe.com

2. **Stripe CLI** (for local testing)
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe

   # Other platforms
   # Visit: https://stripe.com/docs/stripe-cli
   ```

3. **Running Services**
   - MongoDB (localhost:27017 or remote)
   - FastAPI server (localhost:8000)
   - React frontend (localhost:3000) - optional for E2E testing

### Test Coverage Status

| Component | Tests | Status |
|-----------|-------|--------|
| Webhook Repository | 8 integration | ✅ PASS |
| Signature Verification | 18 unit | ✅ PASS |
| Webhook Handler | 10 integration | ✅ PASS |
| Webhook Endpoint | 9 integration | ✅ PASS |
| **TOTAL** | **45 tests** | **All passing** |

---

## Environment Setup

### Step 1: Configure Environment Variables

**File**: `server/.env`

```bash
# Stripe API Keys (from Stripe Dashboard → Developers → API keys)
STRIPE_API_KEY=sk_test_...                    # Secret key (test mode)
STRIPE_PUBLISHABLE_KEY=pk_test_...            # Publishable key (test mode)

# Stripe Webhook Secret (from Stripe Dashboard → Webhooks)
# You'll get this in Step 2 - leave blank for now
STRIPE_WEBHOOK_SECRET=whsec_...               # Webhook signing secret

# Database Configuration
DATABASE_MODE=production                      # Use "test" for testing
MONGODB_URI=mongodb://localhost:27017/translation

# Other required settings
SECRET_KEY=your-secret-key-min-32-chars
```

### Step 2: Verify Database Indexes

The webhook integration requires the `webhook_events` collection with specific indexes. These are automatically created when the server starts.

**Verify indexes are created:**

```bash
# Terminal 1: Start server
cd server
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Check logs for:
# [MongoDB] Webhook events indexes created (90-day TTL)
```

**Manual verification (optional):**

```javascript
// Connect to MongoDB
mongosh mongodb://localhost:27017/translation

// List webhook_events indexes
db.webhook_events.getIndexes()

// Expected indexes:
// 1. event_id_unique (unique: true)
// 2. payment_intent_id_idx
// 3. event_type_idx
// 4. ttl_90_days (expireAfterSeconds: 0)
// 5. created_at_desc
```

### Step 3: Test Database Connection

```bash
# Run quick health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "database": {
    "healthy": true,
    "database": "translation",
    "collections": ["webhook_events", "payments", ...]
  }
}
```

---

## Stripe Dashboard Configuration

### Option A: Test Mode (Local Development)

**1. Get Test Mode API Keys**

- Go to: https://dashboard.stripe.com/test/apikeys
- Copy **Secret key** (starts with `sk_test_`) → Add to `.env` as `STRIPE_API_KEY`
- Copy **Publishable key** (starts with `pk_test_`) → Add to `.env` as `STRIPE_PUBLISHABLE_KEY`

**2. Create Test Webhook Endpoint**

- Go to: https://dashboard.stripe.com/test/webhooks
- Click **Add endpoint**
- **Endpoint URL**: We'll use Stripe CLI for local testing (see next section)
- For now, skip webhook creation - we'll use `stripe listen` command

### Option B: Production Mode (Live Payments)

**1. Get Live Mode API Keys**

- Go to: https://dashboard.stripe.com/apikeys
- Copy **Secret key** (starts with `sk_live_`) → Add to `.env` as `STRIPE_API_KEY`
- Copy **Publishable key** (starts with `pk_live_`) → Add to `.env` as `STRIPE_PUBLISHABLE_KEY`

**2. Create Production Webhook Endpoint**

- Go to: https://dashboard.stripe.com/webhooks
- Click **Add endpoint**
- **Endpoint URL**: `https://yourdomain.com/api/webhooks/stripe`
- **Events to send**: Select these events:
  - `payment_intent.succeeded`
  - `payment_intent.payment_failed`
  - `charge.refunded`
- Click **Add endpoint**
- **Copy Signing Secret** (starts with `whsec_`) → Add to `.env` as `STRIPE_WEBHOOK_SECRET`

**3. Enable HTTPS**

⚠️ **CRITICAL**: Stripe webhooks require HTTPS in production

- Configure SSL/TLS certificate for your domain
- Use reverse proxy (nginx, Caddy) or cloud provider (Heroku, AWS, etc.)
- Stripe will verify HTTPS before sending webhooks

---

## Local Development Testing

### Method 1: Stripe CLI (Recommended)

The Stripe CLI forwards webhook events from Stripe to your local server.

#### Setup

```bash
# 1. Login to Stripe CLI (opens browser)
stripe login

# 2. Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/stripe

# Output shows webhook signing secret:
# > Ready! Your webhook signing secret is whsec_xxx (^C to quit)
```

#### Copy Webhook Secret

```bash
# Terminal output shows:
# > Ready! Your webhook signing secret is whsec_1234567890abcdef...

# Copy the whsec_... value
# Add to server/.env:
STRIPE_WEBHOOK_SECRET=whsec_1234567890abcdef...
```

#### Restart Server (to load new secret)

```bash
# Terminal 3: Restart FastAPI server
cd server
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

#### Trigger Test Events

```bash
# Terminal 4: Send test webhook events

# Test payment success
stripe trigger payment_intent.succeeded

# Test payment failure
stripe trigger payment_intent.payment_failed

# Test refund
stripe trigger charge.refunded

# Custom event (with specific amount)
stripe trigger payment_intent.succeeded --override payment_intent.amount=5000
```

#### Verify Webhook Processing

```bash
# Terminal 2 (stripe listen) shows:
# ✔ Received event payment_intent.succeeded
# → POST http://localhost:8000/api/webhooks/stripe [200]

# Terminal 3 (FastAPI server) shows:
# [WEBHOOK] Received webhook from 127.0.0.1
# [WEBHOOK] Event received: evt_... type=payment_intent.succeeded
# [WEBHOOK] Event evt_... stored in webhook_events
# [WEBHOOK] Handling payment_intent.succeeded: pi_...
# [WEBHOOK] Payment processing triggered for pi_...
# [WEBHOOK] Event evt_... processed successfully
```

#### Check Database

```javascript
// Connect to MongoDB
mongosh mongodb://localhost:27017/translation

// Verify webhook event stored
db.webhook_events.find().sort({created_at: -1}).limit(1).pretty()

// Expected output:
{
  "_id": ObjectId("..."),
  "event_id": "evt_...",
  "event_type": "payment_intent.succeeded",
  "payment_intent_id": "pi_...",
  "raw_payload": { ... },
  "processed": true,
  "processed_at": ISODate("2025-12-05T..."),
  "error": null,
  "created_at": ISODate("2025-12-05T..."),
  "expires_at": ISODate("2026-03-05T...")  // 90 days later
}

// Verify payment created
db.payments.find({webhook_processing: true}).sort({created_at: -1}).limit(1).pretty()

// Expected output:
{
  "_id": ObjectId("..."),
  "stripe_payment_intent_id": "pi_...",
  "amount": 5000,  // in cents
  "currency": "usd",
  "payment_status": "succeeded",
  "webhook_processing": true,
  "webhook_event_id": "evt_...",
  "created_at": ISODate("2025-12-05T...")
}
```

### Method 2: Integration Tests

Run the automated test suite to verify all components:

```bash
cd server

# Set test mode
export DATABASE_MODE=test
# Or edit .env: DATABASE_MODE=test

# Terminal 1: Start test server
DATABASE_MODE=test uvicorn app.main:app --port 8000

# Terminal 2: Run all webhook tests
pytest tests/integration/test_webhook* tests/unit/test_stripe* -v

# Expected output:
# tests/unit/test_stripe_webhook_verification.py::...  18 passed
# tests/integration/test_webhook_repository_integration.py::...  8 passed
# tests/integration/test_webhook_handler_integration.py::...  10 passed
# tests/integration/test_webhooks_endpoint_integration.py::...  9 passed
# ==================== 45 passed in 2.5s ====================
```

### Method 3: Manual HTTP Testing

Test the webhook endpoint directly with curl:

```bash
# 1. Generate valid signature (requires Stripe CLI)
stripe webhook sign \
  --payload '{"id":"evt_test","type":"payment_intent.succeeded","data":{"object":{"id":"pi_test","amount":5000,"currency":"usd","customer_email":"test@example.com"}}}' \
  --secret whsec_your_secret_here

# Output shows:
# signature: t=1234567890,v1=abc123def456...

# 2. Send webhook with signature
curl -X POST http://localhost:8000/api/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "stripe-signature: t=1234567890,v1=abc123def456..." \
  -d '{"id":"evt_test","type":"payment_intent.succeeded","data":{"object":{"id":"pi_test","amount":5000,"currency":"usd","customer_email":"test@example.com"}}}'

# Expected response:
# {"received":true,"event_id":"evt_test"}
```

---

## Testing Checklist

### ✅ Pre-Deployment Testing

**Webhook Endpoint Tests**

- [ ] **Valid signature accepted** - Returns 200 with `{"received": true}`
- [ ] **Invalid signature rejected** - Returns 400 with "Invalid signature"
- [ ] **Missing signature rejected** - Returns 400
- [ ] **Duplicate events handled** - Second event returns 200 (idempotent)
- [ ] **Unsupported events logged** - Returns 200, event stored

**Payment Processing Tests**

- [ ] **payment_intent.succeeded** - Creates payment record, triggers file processing
- [ ] **payment_intent.payment_failed** - Logs error, no payment created
- [ ] **charge.refunded** - Updates payment status to "refunded"

**Fallback Tests**

- [ ] **Webhook wins race** - Client notification sees `webhook_processing=true`, skips
- [ ] **Client wins race** - Webhook sees existing payment, returns duplicate
- [ ] **No duplicate processing** - Only one payment record created

**Database Tests**

- [ ] **Webhook events stored** - Check `webhook_events` collection
- [ ] **90-day TTL works** - Old events have `expires_at` field
- [ ] **Unique constraint enforced** - Duplicate `event_id` rejected
- [ ] **Payment linked to event** - Payment has `webhook_event_id` field

### 🔧 Troubleshooting Tests

**Test invalid signature rejection:**
```bash
# Should return 400
curl -X POST http://localhost:8000/api/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "stripe-signature: invalid" \
  -d '{"id":"evt_test","type":"payment_intent.succeeded"}'
```

**Test duplicate event handling:**
```bash
# Send same event twice with Stripe CLI
stripe trigger payment_intent.succeeded

# Check database - should only have 1 event
mongosh translation --eval "db.webhook_events.countDocuments({event_id: /^evt_/})"
```

**Test signature verification logs:**
```bash
# Server logs should show:
# [WEBHOOK_SECURITY] Invalid signature from IP 127.0.0.1: ...

# For valid signatures:
# [WEBHOOK] Event received: evt_... type=payment_intent.succeeded
```

---

## Production Deployment

### Step 1: Configure Production Webhook

**Stripe Dashboard Setup:**

1. Go to: https://dashboard.stripe.com/webhooks
2. Click **Add endpoint**
3. **Endpoint URL**: `https://yourdomain.com/api/webhooks/stripe`
4. **Events to send**:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.refunded`
5. Click **Add endpoint**
6. **Copy Signing Secret** (starts with `whsec_live_`)

### Step 2: Update Production Environment

```bash
# Production .env
STRIPE_WEBHOOK_SECRET=whsec_live_...  # Production signing secret
STRIPE_API_KEY=sk_live_...             # Live mode secret key
DATABASE_MODE=production
```

### Step 3: Deploy & Verify

**Deploy application:**
```bash
# Example: Deploy to cloud provider
git push heroku main

# Or use CI/CD pipeline
git push origin main
```

**Test production webhook:**
```bash
# Stripe Dashboard → Webhooks → Your endpoint → Send test webhook
# Or create real test payment
```

**Monitor webhook events:**
```bash
# Stripe Dashboard → Developers → Events
# Filter by: endpoint = your production endpoint
# Check: All events show successful delivery (200 response)
```

### Step 4: Monitor Production

**Key metrics to track:**

1. **Webhook success rate**: Target >99%
   ```javascript
   // MongoDB query
   db.webhook_events.aggregate([
     { $group: {
       _id: "$processed",
       count: { $sum: 1 }
     }}
   ])
   ```

2. **Duplicate event rate**: Expected 1-5% (Stripe retries)
   ```javascript
   // Check for duplicate attempts
   db.webhook_events.find({
     event_id: { $regex: /^evt_/ },
     created_at: { $gt: new Date(Date.now() - 86400000) }
   }).count()
   ```

3. **Client notification fallback rate**: Target <5%
   ```bash
   # Server logs
   grep "Already processed by webhook" /var/log/app.log | wc -l
   ```

4. **Security alerts**: Invalid signatures
   ```bash
   # Should be 0 or very low
   grep "WEBHOOK_SECURITY.*Invalid signature" /var/log/app.log
   ```

---

## Troubleshooting

### Issue: Webhooks Not Arriving

**Symptoms:**
- Stripe Dashboard shows webhook attempts failing
- No webhook events in `webhook_events` collection

**Solutions:**

1. **Check HTTPS configuration**
   ```bash
   # Test from Stripe Dashboard → Webhooks → Test webhook
   # If fails with SSL error, check certificate
   curl -v https://yourdomain.com/api/webhooks/stripe
   ```

2. **Verify webhook URL is correct**
   - Should be: `https://yourdomain.com/api/webhooks/stripe`
   - NOT: `http://...` (must use HTTPS)
   - NOT: trailing slash

3. **Check firewall/security groups**
   - Allow inbound traffic from Stripe IPs: https://stripe.com/docs/ips

4. **Test with Stripe CLI**
   ```bash
   # Forward to production server
   stripe listen --forward-to https://yourdomain.com/api/webhooks/stripe
   stripe trigger payment_intent.succeeded
   ```

### Issue: Signature Verification Failing

**Symptoms:**
- Logs show: `[WEBHOOK_SECURITY] Invalid signature`
- Webhooks return 400 status

**Solutions:**

1. **Verify webhook secret is correct**
   ```bash
   # Check .env file
   cat .env | grep STRIPE_WEBHOOK_SECRET

   # Should match secret from Stripe Dashboard
   ```

2. **Check for environment variable reload**
   ```bash
   # Restart server after changing .env
   # FastAPI with --reload should auto-reload, but restart to be sure
   ```

3. **Verify payload not modified**
   - Don't parse/modify request.body() before verification
   - Use raw bytes: `payload = await request.body()`

4. **Check for reverse proxy issues**
   ```bash
   # If using nginx, ensure proxy preserves body:
   proxy_pass http://localhost:8000;
   proxy_set_header X-Forwarded-Proto $scheme;
   ```

### Issue: Duplicate Payments Created

**Symptoms:**
- Same `stripe_payment_intent_id` appears multiple times in `payments` collection

**Solutions:**

1. **Verify unique index exists**
   ```javascript
   // MongoDB
   db.payments.getIndexes()

   // Should have: stripe_payment_intent_id_unique (sparse: true)
   ```

2. **Check idempotency logic**
   ```python
   # payment_simplified.py line ~110
   existing_payment = await payment_repository.get_payment_by_square_id(payment_intent_id)
   if existing_payment:
       return  # Should exit early
   ```

3. **Verify webhook_processing flag**
   ```javascript
   // Check payment record
   db.payments.findOne({stripe_payment_intent_id: "pi_..."})

   // Should have: webhook_processing: true
   ```

### Issue: Client Notification Not Falling Back

**Symptoms:**
- Payment succeeds but client notification doesn't process
- Logs show: "Already processed by webhook" but webhook didn't actually process

**Solutions:**

1. **Check webhook_processing flag logic**
   ```python
   # payment_simplified.py line ~347
   if existing_payment and existing_payment.get("webhook_processing"):
       # Should only skip if webhook actually processed
   ```

2. **Verify webhook completed successfully**
   ```javascript
   // Check webhook event
   db.webhook_events.findOne({payment_intent_id: "pi_..."})

   // Should have: processed: true, error: null
   ```

3. **Check race condition handling**
   - Webhook and client notification can arrive simultaneously
   - First to create payment wins
   - Second should see existing payment and skip

### Issue: Webhook Events Not Expiring (TTL)

**Symptoms:**
- Old webhook events (>90 days) still in database

**Solutions:**

1. **Verify TTL index exists**
   ```javascript
   db.webhook_events.getIndexes()

   // Should have:
   {
     "key": { "expires_at": 1 },
     "name": "ttl_90_days",
     "expireAfterSeconds": 0
   }
   ```

2. **Check MongoDB TTL monitor**
   ```bash
   # MongoDB logs should show TTL deletion
   # TTL monitor runs every 60 seconds
   ```

3. **Manually verify expiration**
   ```javascript
   // Check for expired events
   db.webhook_events.find({
     expires_at: { $lt: new Date() }
   }).count()

   // Should be 0 (or decrease over time as TTL deletes them)
   ```

### Issue: Tests Failing

**Symptoms:**
- Integration tests fail with 404 or connection errors

**Solutions:**

1. **Verify test server is running**
   ```bash
   # Terminal 1: Start server in test mode
   DATABASE_MODE=test uvicorn app.main:app --port 8000

   # Terminal 2: Run tests
   DATABASE_MODE=test pytest tests/integration/ -v
   ```

2. **Check test database connection**
   ```bash
   # Tests should use translation_test database
   mongosh mongodb://localhost:27017/translation_test

   # Verify collections exist
   show collections
   ```

3. **Clear test data between runs**
   ```javascript
   // Clean up test webhook events
   db.webhook_events.deleteMany({event_id: /^TEST_WEBHOOK_/})
   db.payments.deleteMany({stripe_payment_intent_id: /^TEST_WEBHOOK_/})
   ```

---

## Additional Resources

### Stripe Documentation

- **Webhooks Overview**: https://stripe.com/docs/webhooks
- **Webhook Security**: https://stripe.com/docs/webhooks/signatures
- **Test Mode**: https://stripe.com/docs/testing
- **Stripe CLI**: https://stripe.com/docs/stripe-cli

### Internal Documentation

- **API Endpoints**: `server/docs/examples/payments_requests.md`
- **Database Schema**: `server/app/database/mongodb.py` (lines 324-338)
- **Test Examples**: `server/tests/integration/test_webhook*.py`

### Support

**For issues:**
1. Check server logs: `tail -f /var/log/app.log | grep WEBHOOK`
2. Check Stripe Dashboard: Events → Filter by endpoint
3. Run integration tests: `pytest tests/integration/test_webhook* -v`
4. Review this troubleshooting section

**For Stripe-specific issues:**
- Stripe Support: https://support.stripe.com
- Stripe Community: https://github.com/stripe/stripe-python/discussions

---

## Quick Reference

### Environment Variables
```bash
STRIPE_API_KEY=sk_test_...              # Or sk_live_... for production
STRIPE_PUBLISHABLE_KEY=pk_test_...      # Or pk_live_... for production
STRIPE_WEBHOOK_SECRET=whsec_...         # From Stripe Dashboard or CLI
DATABASE_MODE=production                 # Or "test" for testing
MONGODB_URI=mongodb://localhost:27017/translation
```

### Stripe CLI Commands
```bash
stripe login                             # Login to Stripe account
stripe listen --forward-to localhost:8000/api/webhooks/stripe  # Forward webhooks
stripe trigger payment_intent.succeeded  # Send test webhook
stripe webhook sign --payload '{...}'    # Generate signature for manual testing
```

### MongoDB Queries
```javascript
// Recent webhook events
db.webhook_events.find().sort({created_at: -1}).limit(10).pretty()

// Failed events
db.webhook_events.find({processed: true, error: {$ne: null}}).pretty()

// Webhook-processed payments
db.payments.find({webhook_processing: true}).sort({created_at: -1}).limit(10).pretty()

// Check TTL expiration
db.webhook_events.find({expires_at: {$lt: new Date()}}).count()
```

### Test Commands
```bash
# All webhook tests
DATABASE_MODE=test pytest tests/integration/test_webhook* tests/unit/test_stripe* -v

# Specific test
DATABASE_MODE=test pytest tests/integration/test_webhooks_endpoint_integration.py::test_webhook_accepts_valid_signature -v

# With coverage
DATABASE_MODE=test pytest --cov=app.services.webhook_handler --cov=app.routers.webhooks -v
```

---

**Document Version**: 1.0
**Last Updated**: December 5, 2025
**Implementation Status**: ✅ Production Ready (45/45 tests passing)
