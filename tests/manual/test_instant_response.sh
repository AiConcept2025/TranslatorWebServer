#!/bin/bash

# Test script to verify /api/transactions/confirm returns instantly (< 1s)

echo "=========================================="
echo "TEST: Transaction Confirm - Instant Response"
echo "=========================================="
echo ""

# Use a fake token - we expect 401, but we're testing RESPONSE TIME, not auth
TOKEN="test_token_to_measure_response_time"

# Measure response time
echo "⏱️  Sending POST /api/transactions/confirm..."
START=$(date +%s.%N)

curl -s -o /dev/null -w "HTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" \
  -X POST http://localhost:8000/api/transactions/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"transaction_ids": ["TXN-TEST1", "TXN-TEST2", "TXN-TEST3"]}'

END=$(date +%s.%N)
ELAPSED=$(echo "$END - $START" | bc)

echo ""
echo "=========================================="
echo "RESULT:"
echo "=========================================="
echo "Total Time (including network): ${ELAPSED}s"
echo ""

# Check if response was instant (< 1 second)
if (( $(echo "$ELAPSED < 1.0" | bc -l) )); then
    echo "✅ SUCCESS: Endpoint returned in < 1 second"
    echo "   The timeout fix is working!"
else
    echo "❌ FAILURE: Endpoint took > 1 second"
    echo "   Still experiencing timeout/blocking issues"
fi
echo "=========================================="
