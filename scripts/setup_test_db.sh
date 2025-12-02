#!/bin/bash
# =============================================================================
# Setup Test Database Script
# =============================================================================
# This script:
# 1. Dumps the production 'translation' database
# 2. Creates 'translation_test' database
# 3. Restores the dump to 'translation_test'
#
# Usage: ./scripts/setup_test_db.sh
# =============================================================================

set -e  # Exit on any error

# Configuration
MONGO_HOST="localhost"
MONGO_PORT="27017"
MONGO_USER="iris"
MONGO_PASS="Sveta87201120"
AUTH_DB="translation"
SOURCE_DB="translation"
TARGET_DB="translation_test"
DUMP_DIR="/tmp/mongo_dump_$$"

echo "=============================================="
echo "  MongoDB Test Database Setup Script"
echo "=============================================="
echo ""

# Step 1: Create dump directory
echo "[1/4] Creating temporary dump directory..."
mkdir -p "$DUMP_DIR"
echo "      Dump directory: $DUMP_DIR"

# Step 2: Dump the source database
echo ""
echo "[2/4] Dumping '$SOURCE_DB' database..."
mongodump \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --username="$MONGO_USER" \
    --password="$MONGO_PASS" \
    --authenticationDatabase="$AUTH_DB" \
    --db="$SOURCE_DB" \
    --out="$DUMP_DIR"

if [ $? -eq 0 ]; then
    echo "      Dump completed successfully!"
    echo "      Collections dumped:"
    ls -la "$DUMP_DIR/$SOURCE_DB/" | grep -E "\.bson$" | awk '{print "        - " $NF}'
else
    echo "      ERROR: Dump failed!"
    rm -rf "$DUMP_DIR"
    exit 1
fi

# Step 3: Drop existing test database (if exists)
echo ""
echo "[3/4] Dropping existing '$TARGET_DB' database (if exists)..."
mongosh \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --username="$MONGO_USER" \
    --password="$MONGO_PASS" \
    --authenticationDatabase="$AUTH_DB" \
    --quiet \
    --eval "use $TARGET_DB; db.dropDatabase();"

echo "      Done!"

# Step 4: Restore dump to test database
echo ""
echo "[4/4] Restoring dump to '$TARGET_DB' database..."
mongorestore \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --username="$MONGO_USER" \
    --password="$MONGO_PASS" \
    --authenticationDatabase="$AUTH_DB" \
    --db="$TARGET_DB" \
    --drop \
    "$DUMP_DIR/$SOURCE_DB"

if [ $? -eq 0 ]; then
    echo "      Restore completed successfully!"
else
    echo "      ERROR: Restore failed!"
    rm -rf "$DUMP_DIR"
    exit 1
fi

# Cleanup
echo ""
echo "[Cleanup] Removing temporary dump directory..."
rm -rf "$DUMP_DIR"

# Verify
echo ""
echo "=============================================="
echo "  Verification"
echo "=============================================="
echo ""
echo "Collections in '$TARGET_DB':"
mongosh \
    --host="$MONGO_HOST" \
    --port="$MONGO_PORT" \
    --username="$MONGO_USER" \
    --password="$MONGO_PASS" \
    --authenticationDatabase="$AUTH_DB" \
    --quiet \
    --eval "use $TARGET_DB; db.getCollectionNames().forEach(c => print('  - ' + c + ': ' + db.getCollection(c).countDocuments() + ' documents'));"

echo ""
echo "=============================================="
echo "  SUCCESS! Test database is ready."
echo "=============================================="
echo ""
echo "Connection string for tests:"
echo "  mongodb://$MONGO_USER:$MONGO_PASS@$MONGO_HOST:$MONGO_PORT/$TARGET_DB?authSource=$AUTH_DB"
echo ""
