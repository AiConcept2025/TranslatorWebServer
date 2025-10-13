"""
Pytest configuration and fixtures for MongoDB tests.
"""

import pytest
from pymongo import MongoClient
from datetime import datetime, timezone
import sys
import os

# Add parent directory to path to import test_data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_data import TestDataGenerator

# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"


@pytest.fixture(scope="session")
def mongo_client():
    """Create MongoDB client for the entire test session."""
    client = MongoClient(MONGODB_URI)

    # Test connection
    try:
        client.server_info()
        print(f"\n✓ Connected to MongoDB: {DATABASE_NAME}")
    except Exception as e:
        pytest.fail(f"Failed to connect to MongoDB: {e}")

    yield client

    # Cleanup
    client.close()


@pytest.fixture(scope="session")
def db(mongo_client):
    """Get database instance for the entire test session."""
    return mongo_client[DATABASE_NAME]


@pytest.fixture(scope="function")
def test_data_generator():
    """Provide test data generator instance for each test."""
    return TestDataGenerator()


@pytest.fixture(scope="function")
def sample_company(db, test_data_generator):
    """Insert and return a sample company for testing."""
    company_data = test_data_generator.generate_company()
    result = db.company.insert_one(company_data)

    yield company_data

    # Cleanup
    db.company.delete_one({"_id": result.inserted_id})


@pytest.fixture(scope="function")
def sample_user(db, test_data_generator, sample_company):
    """Insert and return a sample company user for testing."""
    user_data = test_data_generator.generate_company_user(sample_company['_id'])
    result = db.company_users.insert_one(user_data)

    yield user_data

    # Cleanup
    db.company_users.delete_one({"_id": result.inserted_id})


@pytest.fixture(scope="function")
def sample_subscription(db, test_data_generator, sample_company):
    """Insert and return a sample subscription for testing."""
    subscription_data = test_data_generator.generate_subscription(sample_company['_id'])
    result = db.subscriptions.insert_one(subscription_data)

    yield subscription_data

    # Cleanup
    db.subscriptions.delete_one({"_id": result.inserted_id})


@pytest.fixture(scope="function")
def full_test_dataset(db):
    """Insert a complete set of test data with proper relationships."""
    generator = TestDataGenerator()
    all_data = generator.generate_all()

    inserted_ids = {}

    # Insert all data (MongoDB will create collections automatically)
    for collection_name, data in all_data.items():
        result = db[collection_name].insert_one(data)
        inserted_ids[collection_name] = result.inserted_id

    yield all_data

    # Cleanup - delete in reverse order to respect foreign keys (6 collections only)
    cleanup_order = [
        'translation_transactions',
        'payments',
        'invoices',
        'subscriptions',
        'company_users',
        'company'
    ]

    for collection_name in cleanup_order:
        if collection_name in inserted_ids:
            db[collection_name].delete_one({"_id": inserted_ids[collection_name]})
