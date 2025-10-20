# Scripts Directory

This directory contains utility and setup scripts for the Translation Service backend.

## Directory Structure

```
scripts/
├── README.md          # This file
├── setup/            # Database and service setup scripts
│   ├── cleanup_db.py
│   ├── seed_data.py
│   ├── setup_collections.py
│   ├── setup_db.py
│   ├── setup_google_drive.py
│   ├── setup_mongodb_collections.py
│   └── setup_mongodb_service.sh
└── utils/            # User and data management utilities
    ├── create_admin_user.py
    ├── create_test_user.py
    ├── create_translations.py
    ├── create_users.py
    ├── fix_test_subscription.py
    ├── query_translations_summary.py
    ├── verify_admin_login.py
    └── verify_translations.py
```

## Setup Scripts (`setup/`)

### Database Setup
- `setup_mongodb_service.sh` - Install and configure MongoDB service
- `setup_mongodb_collections.py` - Create MongoDB collections and indexes
- `setup_collections.py` - Alternative collection setup script
- `setup_db.py` - Initialize database schema

### Data Management
- `seed_data.py` - Populate database with seed data
- `cleanup_db.py` - Clean up test data and reset database

### Services
- `setup_google_drive.py` - Configure Google Drive integration

## Utility Scripts (`utils/`)

### User Management
- `create_admin_user.py` - Create administrator users
- `create_test_user.py` - Create test user accounts
- `create_users.py` - Bulk user creation utility
- `verify_admin_login.py` - Verify admin authentication

### Subscription Management
- `fix_test_subscription.py` - Fix/reset test subscription data

### Data Queries
- `query_translations_summary.py` - Query translation statistics
- `verify_translations.py` - Verify translation data integrity
- `create_translations.py` - Create test translation records

## Usage

### First-Time Setup
```bash
# 1. Install MongoDB
cd scripts/setup
./setup_mongodb_service.sh

# 2. Create collections
python setup_mongodb_collections.py

# 3. Seed initial data
python seed_data.py

# 4. Create admin user
cd ../utils
python create_admin_user.py
```

### Common Operations
```bash
# Create test user
python scripts/utils/create_test_user.py

# Fix subscription issues
python scripts/utils/fix_test_subscription.py

# Query translation data
python scripts/utils/query_translations_summary.py

# Verify admin login
python scripts/utils/verify_admin_login.py
```

## Notes
- All scripts should be run from the server root directory
- Ensure virtual environment is activated: `source venv/bin/activate`
- Scripts require MongoDB to be running
- Check individual script headers for specific requirements
