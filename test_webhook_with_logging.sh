#!/bin/bash

# Test webhook with detailed logging
# This script sends a webhook request and we should see detailed logging in server console

echo "================================================================================"
echo "WEBHOOK TEST - Verifying Enhanced Logging"
echo "================================================================================"
echo ""

# Transaction details
TRANSACTION_ID="TXN-E4E38F3A75"
FILE_NAME="Cable_Management_Changes_PRD.docx"
FILE_URL="https://drive.google.com/file/d/1TEST_TRANSLATED_WEBHOOK/view"
USER_EMAIL="danishevsky@yahoo.com"

echo "Sending webhook for:"
echo "  Transaction: $TRANSACTION_ID"
echo "  File: $FILE_NAME"
echo "  URL: $FILE_URL"
echo ""

curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d "{
    \"transaction_id\": \"$TRANSACTION_ID\",
    \"file_name\": \"$FILE_NAME\",
    \"file_url\": \"$FILE_URL\",
    \"user_email\": \"$USER_EMAIL\",
    \"company_name\": \"Ind\"
  }" \
  -w "\n\nHTTP Status: %{http_code}\n" | python3 -m json.tool 2>/dev/null || cat

echo ""
echo "================================================================================"
echo "CHECK SERVER LOGS"
echo "================================================================================"
echo ""
echo "You should now see detailed logging in the server console including:"
echo "  - SUBMIT ENDPOINT - Incoming Request"
echo "  - SUBMIT SERVICE - Processing Submission"
echo "  - TRANSACTION UPDATE SERVICE - Individual Transaction"
echo "  - DOCUMENT LOOKUP - Starting Detailed Comparison"
echo "  - PREPARING DATABASE UPDATE"
echo "  - DATABASE UPDATE RESULT"
echo "  - EMAIL BATCHING GATE CHECK"
echo ""
