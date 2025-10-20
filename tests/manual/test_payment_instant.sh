#!/bin/bash

# Test script to verify instant payment response

echo "============================================"
echo "Testing Payment Success Endpoint"
echo "============================================"
echo ""

# Test data
CUSTOMER_EMAIL="test@example.com"
PAYMENT_INTENT="payment_test_12345"

echo "1. Testing instant response (should return < 1 second)..."
echo ""

START_TIME=$(date +%s.%N)

curl -X POST http://localhost:8000/api/payment/success \
  -H "Content-Type: application/json" \
  -d "{
    \"customer_email\": \"$CUSTOMER_EMAIL\",
    \"paymentIntentId\": \"$PAYMENT_INTENT\",
    \"amount\": 10.00,
    \"currency\": \"USD\",
    \"paymentMethod\": \"card\"
  }" \
  -w "\n\n⏱️  Response Time: %{time_total}s\n" \
  -s

END_TIME=$(date +%s.%N)
ELAPSED=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "============================================"
echo "Test Complete"
echo "Total elapsed time: ${ELAPSED}s"
echo "============================================"

if (( $(echo "$ELAPSED < 2" | bc -l) )); then
    echo "✅ PASS: Response time < 2 seconds (instant!)"
else
    echo "❌ FAIL: Response time >= 2 seconds (still slow)"
fi

echo ""
echo "Check server logs for:"
echo "  - ⚡ INSTANT PAYMENT SUCCESS WEBHOOK"
echo "  - ⚡ INSTANT RESPONSE - Background task scheduled"
echo "  - 🔄 BACKGROUND TASK STARTED (after response)"
