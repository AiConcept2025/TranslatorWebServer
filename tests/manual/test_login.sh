#!/bin/bash

# Test corporate login
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "companyName": "Iris Trading",
  "password": "Sveta87201120!",
  "userFullName": "Vladimir L Danishevsky",
  "userEmail": "danishevsky@gmail.com",
  "loginDateTime": "2025-01-13T10:30:00Z"
}
EOF
