# Payment Endpoint - Complete Logging Example

## Full Server Console Output

When a payment webhook is received, the server now logs **complete incoming and outgoing messages**.

### Example: Actual Client Payload

```
================================================================================
💳 PAYMENT SUCCESS WEBHOOK - INCOMING REQUEST
================================================================================
📥 INCOMING PAYLOAD:
{"paymentIntentId": "payment_sq_1760060540428_wq00qen6d", "amount": 0.1, "currency": "USD", "paymentMethod": "square", "metadata": {"status": "COMPLETED", "cardBrand": "VISA", "last4": "5220", "receiptNumber": "PAYMENT_SQ_1760060540428_WQ00QEN6D", "created": "2025-10-10T01:42:20.429Z", "simulated": true, "customer_email": "test@example.com"}, "timestamp": "2025-10-10T01:42:20.430Z"}

📋 PARSED JSON:
{
  "paymentIntentId": "payment_sq_1760060540428_wq00qen6d",
  "amount": 0.1,
  "currency": "USD",
  "paymentMethod": "square",
  "metadata": {
    "status": "COMPLETED",
    "cardBrand": "VISA",
    "last4": "5220",
    "receiptNumber": "PAYMENT_SQ_1760060540428_WQ00QEN6D",
    "created": "2025-10-10T01:42:20.429Z",
    "simulated": true,
    "customer_email": "test@example.com"
  },
  "timestamp": "2025-10-10T01:42:20.430Z"
}

--------------------------------------------------------------------------------
✅ PARSED FIELDS:
--------------------------------------------------------------------------------
Customer Email:    test@example.com
Payment Intent ID: payment_sq_1760060540428_wq00qen6d
Amount:            $0.1 USD
Payment Method:    square
Timestamp:         2025-10-10T01:42:20.430Z

Metadata:
  Status:         COMPLETED
  Card Brand:     VISA
  Last 4 Digits:  5220
  Receipt Number: PAYMENT_SQ_1760060540428_WQ00QEN6D
  Created:        2025-10-10T01:42:20.429Z
  Simulated:      True
--------------------------------------------------------------------------------

⚠️  No pending files found for customer

================================================================================
📤 OUTGOING RESPONSE:
================================================================================
{
  "success": true,
  "message": "Payment confirmed but no pending files found",
  "data": {
    "customer_email": "test@example.com",
    "payment_intent_id": "payment_sq_1760060540428_wq00qen6d",
    "files_moved": 0
  }
}
================================================================================
```

## Log Sections

### 1. **Incoming Request** 📥
- Raw JSON payload (single line)
- Pretty-printed JSON (formatted)

### 2. **Parsed Fields** ✅
- All extracted values displayed clearly
- Customer email (from metadata or root)
- Payment details
- All metadata fields

### 3. **Processing Status** 🔄
- File search results
- File move operations
- Status updates
- Any warnings or errors

### 4. **Outgoing Response** 📤
- Complete JSON response
- Shows exactly what client receives

## Benefits

✅ **Complete audit trail** - Every field is logged
✅ **Easy debugging** - See raw payload and parsed values
✅ **Request/Response tracking** - Full incoming/outgoing visibility
✅ **Error diagnosis** - Clear error messages with context

## Log Locations

All logs print to **stdout** (console) and are visible in:
- Terminal where server is running
- Docker logs (if containerized)
- Log aggregation tools (if configured)

## What Gets Logged

**Every Request:**
- ✓ Raw incoming JSON
- ✓ Parsed JSON (formatted)
- ✓ All extracted fields
- ✓ Metadata contents
- ✓ Processing steps
- ✓ Complete response JSON

**On Error:**
- ✓ Error type and message
- ✓ Stack trace
- ✓ Failed validation details
- ✓ Error response sent to client
