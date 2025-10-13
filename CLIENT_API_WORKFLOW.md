# SIMPLIFIED Client API Workflow Guide

This document describes the **SIMPLIFIED** sequence of API calls for the Translation Web Server client integration.

## 🔄 SIMPLIFIED Workflow Overview

```
1. Upload Files → 2. Process Payment → 3. Payment Success Webhook → Files Moved to Inbox
```

**✅ REMOVED**: Complex payment session registration step

---

## 1. 📤 File Upload

### Endpoint
```
POST /translate
```

### Required Headers
```
Content-Type: application/json
```

### Required Parameters
```json
{
  "files": [
    {
      "id": "string",
      "name": "string", 
      "size": number,
      "type": "string"
    }
  ],
  "sourceLanguage": "string",
  "targetLanguage": "string", 
  "email": "string",
  "paymentIntentId": "string (optional)"
}
```

### Example Request
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "id": "temp_file_1",
        "name": "document.docx",
        "size": 19863,
        "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      }
    ],
    "sourceLanguage": "ru",
    "targetLanguage": "en",
    "email": "customer@example.com"
  }'
```

### Response Format
```json
{
  "success": true,
  "data": {
    "pricing": {
      "total_pages": 3,
      "price_per_page": 0.10,
      "total_amount": 0.30,
      "currency": "USD"
    },
    "files": {
      "total_files": 1,
      "successful_uploads": 1,
      "failed_uploads": 0
    },
    "customer": {
      "email": "customer@example.com",
      "source_language": "ru",
      "target_language": "en"
    },
    "payment": {
      "required": true,
      "amount_cents": 30,
      "customer_email": "customer@example.com"
    }
  }
}
```

### ⚠️ Important Notes
- Files are uploaded to **Temp** folder with `status: "awaiting_payment"`
- Extract `payment.customer_email` for payment processing
- Files will **NOT** be moved to Inbox until payment is completed

---

## 2. 💰 Process Payment

### Payment Processing
This step is handled by your payment provider (Square, Stripe, etc.). The client needs to:

1. Create payment intent with your payment provider
2. Process the payment using the payment provider's SDK/API  
3. Include `customer_email` in payment metadata for webhook linking

### Example Payment Intent IDs
- Square: `sq_1759969472044_ax17b12ky`
- Stripe: `pi_1234567890abcdef`
- Custom: `payment_custom_12345`

---

## 3. ✅ Payment Success Webhook

### Endpoint
```
POST /api/payment/success
```

### Required Headers
```
Content-Type: application/json
```

### SIMPLIFIED Webhook Format
```json
{
  "customer_email": "customer@example.com",
  "payment_intent_id": "pi_1234567890"
}
```

### Example Webhook Request
```bash
curl -X POST http://localhost:8000/api/payment/success \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "customer@example.com",
    "payment_intent_id": "pi_1234567890"
  }'
```

### Response Format
```json
{
  "success": true,
  "message": "Payment confirmed. 1 files moved to Inbox.",
  "data": {
    "customer_email": "customer@example.com",
    "payment_intent_id": "pi_1234567890",
    "total_files": 1,
    "moved_successfully": 1,
    "inbox_folder_id": "1CjRJIUSr-JYUVpReU9T8iK0lq2Vv6GPb"
  }
}
```

### ⚠️ Important Notes
- This is typically called automatically by payment provider webhooks
- Files are moved from **Temp** to **Inbox** folder
- Payment session is cleaned up after successful processing

---

## 🚨 Common Error Scenarios

### Error 1: 422 Validation Error (Payment Session Registration)
**Cause**: Wrong data format or missing fields

**Solution**: Check that you're sending:
- `customer_email` (valid email string)
- `file_ids` (array of strings) 
- `payment_intent_id` (non-empty string)

### Error 2: 404 Payment Session Not Found
**Cause**: Payment webhook called without registering session first

**Solution**: Ensure step 2 (Register Payment Session) is completed before payment processing

### Error 3: Duplicate Files in Temp Folder
**Cause**: Client sending multiple requests

**Solution**: Implement client-side request deduplication and proper error handling

---

## 🛠️ Testing Endpoints

### Debug Temp Folder Contents
```bash
curl "http://localhost:8000/api/payment/debug-temp-folder?customer_email=customer@example.com"
```

### List Active Payment Sessions
```bash
curl "http://localhost:8000/api/payment/sessions"
```

### Clean Up Temp Folder
```bash
curl -X POST "http://localhost:8000/api/payment/cleanup-temp-folder?customer_email=customer@example.com"
```

### Complete Workflow Test
```bash
curl -X POST http://localhost:8000/api/payment/complete-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "customer@example.com",
    "file_ids": ["1ABC123_google_drive_id"],
    "payment_intent_id": "pi_test_workflow"
  }'
```

---

## 📋 Client Implementation Checklist

- [ ] **Step 1**: Upload files using `/translate` endpoint
- [ ] **Step 2**: Extract `payment_info` from upload response
- [ ] **Step 3**: Register payment session using `/api/payment/register-session`
- [ ] **Step 4**: Process payment with payment provider
- [ ] **Step 5**: Ensure webhook calls `/api/payment/success` with correct `paymentIntentId`
- [ ] **Error Handling**: Implement proper retry logic with backoff
- [ ] **Deduplication**: Prevent multiple requests for same operation
- [ ] **Validation**: Validate all required fields before sending requests

---

## 🎯 Key Success Factors

1. **Correct Sequence**: Follow the 4-step workflow in order
2. **Data Consistency**: Use the same `payment_intent_id` across steps 2-4
3. **Field Names**: Use exact field names (snake_case for registration, camelCase for webhooks)
4. **Error Handling**: Check response status and handle errors appropriately
5. **Session Management**: Register payment session before processing payment

---

## 📞 Support

If you encounter issues:

1. Check the enhanced logging output for detailed error information
2. Use the debug endpoints to inspect current state
3. Verify all required fields are present and correctly formatted
4. Ensure the workflow sequence is followed exactly