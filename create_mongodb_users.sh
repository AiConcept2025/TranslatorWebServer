#!/bin/bash

# ================================================
# MongoDB User Creation Script
# Assumes MongoDB is already installed and running
# ================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_step() { echo -e "${BLUE}➜ $1${NC}"; }

# Default values
DB_NAME="translation"
DB_HOST="localhost"
DB_PORT="27017"
CREATE_ADMIN_USER=false
CREATE_DB_USER=false
ADMIN_USERNAME=""
ADMIN_PASSWORD=""
DB_USERNAME=""
DB_PASSWORD=""

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  --admin USERNAME PASSWORD    Create MongoDB admin user
  --user USERNAME PASSWORD     Create database user
  -h, --host HOST             MongoDB host (default: localhost)
  -P, --port PORT             MongoDB port (default: 27017)
  -d, --database NAME         Database name (default: translation)
  --help                      Show this help message

Examples:
  # Create only admin user
  $0 --admin vlad password1

  # Create only database user
  $0 --user iris password2

  # Create both users
  $0 --admin vlad password1 --user iris password2

  # With custom database
  $0 --admin vlad password1 --user iris password2 -d mydb

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --admin)
            if [ $# -lt 3 ]; then
                print_error "--admin requires username and password"
                exit 1
            fi
            CREATE_ADMIN_USER=true
            ADMIN_USERNAME="$2"
            ADMIN_PASSWORD="$3"
            shift 3
            ;;
        --user)
            if [ $# -lt 3 ]; then
                print_error "--user requires username and password"
                exit 1
            fi
            CREATE_DB_USER=true
            DB_USERNAME="$2"
            DB_PASSWORD="$3"
            shift 3
            ;;
        -h|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -P|--port)
            DB_PORT="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate
if [ "$CREATE_ADMIN_USER" = false ] && [ "$CREATE_DB_USER" = false ]; then
    print_error "You must specify at least one user to create"
    echo ""
    echo "Use --admin USERNAME PASSWORD or --user USERNAME PASSWORD"
    echo "Run with --help for more information"
    exit 1
fi

echo "================================================================"
echo "         MongoDB User Creation Script"
echo "================================================================"
echo ""

print_info "Configuration:"
echo "  MongoDB: $DB_HOST:$DB_PORT"
echo "  Database: $DB_NAME"
if [ "$CREATE_ADMIN_USER" = true ]; then
    echo "  Admin User: $ADMIN_USERNAME"
fi
if [ "$CREATE_DB_USER" = true ]; then
    echo "  Database User: $DB_USERNAME"
fi
echo ""

# Check mongosh
print_step "Checking MongoDB Shell..."
if ! command -v mongosh &> /dev/null; then
    print_error "mongosh not found"
    print_info "Install mongosh: https://www.mongodb.com/docs/mongodb-shell/install/"
    exit 1
fi
print_success "mongosh found"

# Test connection
print_step "Testing MongoDB connection..."
if ! mongosh --host "$DB_HOST" --port "$DB_PORT" --eval "db.version()" >/dev/null 2>&1; then
    print_error "Cannot connect to MongoDB at $DB_HOST:$DB_PORT"
    print_info "Make sure MongoDB is running"
    exit 1
fi
print_success "MongoDB connection successful"
echo ""

# Check authentication status
AUTH_ENABLED=false
if mongosh --host "$DB_HOST" --port "$DB_PORT" --eval "db.version()" >/dev/null 2>&1; then
    print_warning "MongoDB authentication is NOT enabled"
else
    AUTH_ENABLED=true
    print_info "MongoDB authentication is enabled"
fi
echo ""

# Create admin user
if [ "$CREATE_ADMIN_USER" = true ]; then
    print_step "Creating MongoDB admin user: $ADMIN_USERNAME"
    
    mongosh --host "$DB_HOST" --port "$DB_PORT" --quiet << EOF
use admin
try {
  db.createUser({
    user: "$ADMIN_USERNAME",
    pwd: "$ADMIN_PASSWORD",
    roles: [
      { role: "userAdminAnyDatabase", db: "admin" },
      { role: "readWriteAnyDatabase", db: "admin" },
      { role: "dbAdminAnyDatabase", db: "admin" }
    ]
  });
  print("✓ Admin user '$ADMIN_USERNAME' created");
} catch (e) {
  if (e.code === 51003) {
    db.changeUserPassword("$ADMIN_USERNAME", "$ADMIN_PASSWORD");
    print("✓ Admin user '$ADMIN_USERNAME' already exists, password updated");
  } else {
    print("✗ Error: " + e.message);
    quit(1);
  }
}
EOF
    
    if [ $? -eq 0 ]; then
        print_success "Admin user created/updated"
    else
        print_error "Failed to create admin user"
        exit 1
    fi
    echo ""
fi

# Create database user
if [ "$CREATE_DB_USER" = true ]; then
    print_step "Creating database user: $DB_USERNAME for database: $DB_NAME"
    
    # Determine connection method
    if [ "$CREATE_ADMIN_USER" = true ]; then
        # Use admin credentials just created
        CONNECTION="mongosh --host $DB_HOST --port $DB_PORT -u $ADMIN_USERNAME -p $ADMIN_PASSWORD --authenticationDatabase admin"
    elif [ "$AUTH_ENABLED" = true ]; then
        # Need existing admin credentials
        print_warning "MongoDB has authentication enabled"
        print_info "Need admin credentials to create database user"
        read -p "Admin Username: " EXISTING_ADMIN_USER
        read -sp "Admin Password: " EXISTING_ADMIN_PASS
        echo ""
        CONNECTION="mongosh --host $DB_HOST --port $DB_PORT -u $EXISTING_ADMIN_USER -p $EXISTING_ADMIN_PASS --authenticationDatabase admin"
    else
        # No auth
        CONNECTION="mongosh --host $DB_HOST --port $DB_PORT"
    fi
    
    $CONNECTION --quiet << EOF
use $DB_NAME
try {
  db.createUser({
    user: "$DB_USERNAME",
    pwd: "$DB_PASSWORD",
    roles: [
      { role: "readWrite", db: "$DB_NAME" },
      { role: "dbAdmin", db: "$DB_NAME" }
    ]
  });
  print("✓ Database user '$DB_USERNAME' created");
} catch (e) {
  if (e.code === 51003) {
    db.changeUserPassword("$DB_USERNAME", "$DB_PASSWORD");
    print("✓ Database user '$DB_USERNAME' already exists, password updated");
  } else {
    print("✗ Error: " + e.message);
    quit(1);
  }
}
EOF
    
    if [ $? -eq 0 ]; then
        print_success "Database user created/updated"
    else
        print_error "Failed to create database user"
        exit 1
    fi
    echo ""
fi

# Summary
echo "================================================================"
print_success "User Creation Complete!"
echo "================================================================"
echo ""

if [ "$CREATE_ADMIN_USER" = true ]; then
    echo "MongoDB Admin User:"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: $ADMIN_PASSWORD"
    echo "  Database: admin"
    echo "  Roles: userAdminAnyDatabase, readWriteAnyDatabase, dbAdminAnyDatabase"
    echo ""
fi

if [ "$CREATE_DB_USER" = true ]; then
    echo "Database User:"
    echo "  Username: $DB_USERNAME"
    echo "  Password: $DB_PASSWORD"
    echo "  Database: $DB_NAME"
    echo "  Roles: readWrite, dbAdmin"
    echo ""
    echo "Connection String:"
    echo "  mongodb://$DB_USERNAME:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME?authSource=$DB_NAME"
    echo ""
fi

# Save credentials
CREDS_FILE="mongodb_credentials_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "MongoDB Credentials - $(date)"
    echo "================================"
    echo ""
    echo "MongoDB: $DB_HOST:$DB_PORT"
    echo "Database: $DB_NAME"
    echo ""
    if [ "$CREATE_ADMIN_USER" = true ]; then
        echo "Admin User:"
        echo "  Username: $ADMIN_USERNAME"
        echo "  Password: $ADMIN_PASSWORD"
        echo "  Database: admin"
        echo ""
    fi
    if [ "$CREATE_DB_USER" = true ]; then
        echo "Database User:"
        echo "  Username: $DB_USERNAME"
        echo "  Password: $DB_PASSWORD"
        echo "  Database: $DB_NAME"
        echo "  Connection: mongodb://$DB_USERNAME:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME?authSource=$DB_NAME"
        echo ""
    fi
} > "$CREDS_FILE"

chmod 600 "$CREDS_FILE"
print_success "Credentials saved to: $CREDS_FILE"
echo ""

if [ "$AUTH_ENABLED" = false ]; then
    print_warning "SECURITY WARNING"
    echo "MongoDB authentication is NOT enabled!"
    echo "To enable it:"
    echo "  1. Edit your mongod.conf"
    echo "  2. Add:"
    echo "     security:"
    echo "       authorization: enabled"
    echo "  3. Restart MongoDB"
    echo ""
fi

