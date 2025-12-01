#!/bin/bash

# MongoDB Backup Script for Translation Database
# Creates timestamped dumps of the translation database

set -e  # Exit on error

# Configuration
DB_NAME="translation"
DB_HOST="localhost"
DB_PORT="27017"
BACKUP_DIR="$(dirname "$0")/../backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILENAME="translation_dump_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print header
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}MongoDB Backup Script${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Create backup directory if it doesn't exist
if [ ! -d "$BACKUP_DIR" ]; then
    echo "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Check if mongodump is available
if ! command -v mongodump &> /dev/null; then
    echo -e "${RED}ERROR: mongodump command not found${NC}"
    echo "Please install MongoDB Database Tools:"
    echo "  - macOS: brew install mongodb/brew/mongodb-database-tools"
    echo "  - Linux: apt-get install mongodb-database-tools"
    echo "  - Or download from: https://www.mongodb.com/try/download/database-tools"
    exit 1
fi

# Check if MongoDB is running
if ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to MongoDB at ${DB_HOST}:${DB_PORT}${NC}"
    echo "Please ensure MongoDB is running."
    exit 1
fi

# Perform backup
echo "Starting backup..."
echo "Database: $DB_NAME"
echo "Host: ${DB_HOST}:${DB_PORT}"
echo "Output: $BACKUP_PATH"
echo ""

if mongodump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --db="$DB_NAME" \
    --out="$BACKUP_PATH" \
    --quiet; then

    # Success
    echo ""
    echo -e "${GREEN}✓ Backup completed successfully!${NC}"
    echo ""
    echo "Backup details:"
    echo "  Location: $BACKUP_PATH"
    echo "  Size: $(du -sh "$BACKUP_PATH" | cut -f1)"
    echo "  Created: $(date)"
    echo ""

    # Optional: Compress the backup
    echo "Compressing backup..."
    if tar -czf "${BACKUP_PATH}.tar.gz" -C "$BACKUP_DIR" "$BACKUP_FILENAME" 2>/dev/null; then
        rm -rf "$BACKUP_PATH"
        echo -e "${GREEN}✓ Backup compressed: ${BACKUP_FILENAME}.tar.gz${NC}"
        echo "  Compressed size: $(du -sh "${BACKUP_PATH}.tar.gz" | cut -f1)"
    else
        echo -e "${YELLOW}Warning: Compression failed, keeping uncompressed backup${NC}"
    fi

    echo ""
    echo -e "${GREEN}Backup process completed!${NC}"
    echo ""

    # Show recent backups
    echo "Recent backups in $BACKUP_DIR:"
    ls -lht "$BACKUP_DIR" | head -n 6

    exit 0
else
    # Failure
    echo ""
    echo -e "${RED}✗ Backup failed!${NC}"
    echo "Please check MongoDB connection and permissions."
    exit 1
fi
