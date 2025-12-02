#!/bin/bash

# Script to update user passwords in MongoDB with bcrypt hashing
# Usage: ./scripts/update_db_password.sh <collection_name> <email> <password>

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validate arguments
if [ "$#" -ne 3 ]; then
    echo -e "${RED}Error: Invalid number of arguments${NC}"
    echo ""
    echo "Usage: $0 <collection_name> <email> <password>"
    echo ""
    echo "Supported collections:"
    echo "  - iris-admins         (fields: user_email, password)"
    echo "  - company_users       (fields: email, password_hash)"
    echo "  - users_login         (fields: user_email, password)"
    echo ""
    echo "Examples:"
    echo "  $0 iris-admins danishevsky@gmail.com password123"
    echo "  $0 company_users sam.danishevsky@gmail.com password123"
    echo "  $0 users_login sam.danishevsky@iris-translation.com password123"
    exit 1
fi

COLLECTION_NAME="$1"
EMAIL="$2"
PASSWORD="$3"

# MongoDB connection details - uses PRODUCTION database (translation)
MONGO_URI="mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DB_NAME="translation"

# Validate collection name and set field names
case "$COLLECTION_NAME" in
    "iris-admins")
        EMAIL_FIELD="user_email"
        PASSWORD_FIELD="password"
        ;;
    "company_users")
        EMAIL_FIELD="email"
        PASSWORD_FIELD="password_hash"
        ;;
    "users_login")
        EMAIL_FIELD="user_email"
        PASSWORD_FIELD="password"
        ;;
    *)
        echo -e "${RED}Error: Unsupported collection name: $COLLECTION_NAME${NC}"
        echo "Supported collections: iris-admins, company_users, users_login"
        exit 1
        ;;
esac

echo -e "${YELLOW}Hashing password with bcrypt...${NC}"

# Hash password using Python bcrypt
HASHED_PASSWORD=$(python3 -c "
import bcrypt
import sys

password = sys.argv[1]
# Generate salt and hash password
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
# Output hash as string (decode from bytes)
print(hashed.decode('utf-8'))
" "$PASSWORD")

if [ -z "$HASHED_PASSWORD" ]; then
    echo -e "${RED}Error: Failed to hash password${NC}"
    echo "Make sure Python 3 and bcrypt are installed: pip install bcrypt"
    exit 1
fi

echo -e "${GREEN}Password hashed successfully${NC}"
echo -e "${YELLOW}Updating database...${NC}"

# Update MongoDB using mongosh
UPDATE_RESULT=$(mongosh "$MONGO_URI" --quiet --eval "
db = db.getSiblingDB('$DB_NAME');
result = db.getCollection('$COLLECTION_NAME').updateOne(
    { '$EMAIL_FIELD': '$EMAIL' },
    { \$set: { '$PASSWORD_FIELD': '$HASHED_PASSWORD' } }
);
print(JSON.stringify({
    matched: result.matchedCount,
    modified: result.modifiedCount
}));
")

# Parse result
MATCHED=$(echo "$UPDATE_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('matched', 0))")
MODIFIED=$(echo "$UPDATE_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('modified', 0))")

# Report results
echo ""
if [ "$MATCHED" -eq 0 ]; then
    echo -e "${RED}Failed: No user found with email '$EMAIL' in collection '$COLLECTION_NAME'${NC}"
    exit 1
elif [ "$MODIFIED" -eq 1 ]; then
    echo -e "${GREEN}Success: Password updated for '$EMAIL' in '$COLLECTION_NAME'${NC}"
    echo -e "${GREEN}Field updated: $PASSWORD_FIELD${NC}"
    exit 0
else
    echo -e "${YELLOW}Warning: User found but password was not modified (may already be the same)${NC}"
    echo -e "Matched: $MATCHED, Modified: $MODIFIED"
    exit 0
fi
