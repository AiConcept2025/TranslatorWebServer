#!/bin/bash

# Test script to verify enhanced webhook logging
# This script triggers the webhook endpoint and shows the enhanced logging output

echo "================================================================================"
echo "WEBHOOK LOGGING TEST - Simulating GoogleTranslator Callback"
echo "================================================================================"
echo ""

# Check if server is running
echo "Checking if server is running on localhost:8000..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ ERROR: Server is not running on localhost:8000"
    echo "Please start the server with: uvicorn app.main:app --reload --port 8000"
    exit 1
fi
echo "✅ Server is running"
echo ""

# Test with existing transaction
TRANSACTION_ID="USER370191"
FILE_NAME="NuVIZ_Cable_Management_Market_Comparison_Report.docx"
FILE_URL="https://drive.google.com/file/d/TEST_TRANSLATED_123/view"
USER_EMAIL="danishevsky@yahoo.com"

echo "Test Parameters:"
echo "  Transaction ID: $TRANSACTION_ID"
echo "  File Name: $FILE_NAME"
echo "  File URL: $FILE_URL"
echo "  User Email: $USER_EMAIL"
echo ""

echo "================================================================================"
echo "SENDING WEBHOOK REQUEST"
echo "================================================================================"
echo ""

# Send webhook request
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d "{
    \"transaction_id\": \"$TRANSACTION_ID\",
    \"file_name\": \"$FILE_NAME\",
    \"file_url\": \"$FILE_URL\",
    \"user_email\": \"$USER_EMAIL\",
    \"company_name\": \"Ind\"
  }" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  2>&1 | jq '.' 2>/dev/null || cat

echo ""
echo "================================================================================"
echo "CHECK SERVER LOGS FOR DETAILED OUTPUT"
echo "================================================================================"
echo ""
echo "Look for these log sections:"
echo "  1. WEBHOOK RECEIVED - GoogleTranslator Callback"
echo "  2. ✅ DOCUMENT MATCH FOUND!"
echo "  3. PREPARING DATABASE UPDATE (Individual)"
echo "  4. DATABASE UPDATE RESULT"
echo "  5. EMAIL BATCHING GATE CHECK"
echo "  6. SENDING EMAIL - Content Preview"
echo "  7. EMAIL SEND RESULT"
echo ""
echo "✅ Test complete - check server logs for enhanced logging output"
