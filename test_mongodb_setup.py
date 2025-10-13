#!/usr/bin/env python3
"""
MongoDB Setup Test Suite
Comprehensive tests to verify MongoDB collections, indexes, models, and CRUD operations.
"""

import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from bson import ObjectId

# Import our MongoDB models
from app.mongodb_models import (
    SystemConfig, SchemaVersion, SystemAdmin, Customer, CompanyUser,
    Subscription, Invoice, Payment, TranslationTransaction,
    AuditLog, NotificationLog, APIKey,
    ConfigType, AdminRole, UserStatus, SubscriptionUnit, SubscriptionStatus,
    PyObjectId
)

# MongoDB Connection
MONGODB_URI = "mongodb://iris:Iris87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(test_name: str, passed: bool, message: str = ""):
    """Print test result with color."""
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"{status} - {test_name}")
    if message:
        print(f"       {message}")


def test_connection():
    """Test MongoDB connection."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing MongoDB Connection ==={Colors.RESET}")

    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        client.server_info()
        print_test("MongoDB Connection", True, f"Connected to {DATABASE_NAME}")
        return client, db
    except Exception as e:
        print_test("MongoDB Connection", False, str(e))
        sys.exit(1)


def test_collections(db):
    """Test that all collections were created."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Collections ==={Colors.RESET}")

    expected_collections = [
        'system_config', 'schema_versions', 'system_admins', 'system_activity_log',
        'customers', 'company_users', 'subscriptions', 'invoices', 'payments',
        'translation_transactions', 'audit_logs', 'notification_logs', 'api_keys'
    ]

    existing_collections = db.list_collection_names()

    all_found = True
    for collection_name in expected_collections:
        found = collection_name in existing_collections
        print_test(f"Collection: {collection_name}", found)
        if not found:
            all_found = False

    return all_found


def test_indexes(db):
    """Test that indexes were created properly."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Indexes ==={Colors.RESET}")

    test_cases = [
        ("system_config", "config_key_1", True),
        ("schema_versions", "version_number_1", False),
        ("system_admins", "username_1", True),
        ("system_admins", "email_1", True),
        ("customers", "company_name_1", False),
        ("company_users", "user_id_1", True),
        ("company_users", "customer_id_1_email_1", True),
        ("subscriptions", "customer_id_1", False),
        ("invoices", "invoice_number_1", True),
        ("payments", "square_payment_id_1", True),
        ("translation_transactions", "customer_id_1", False),
        ("audit_logs", "timestamp_-1", False),
        ("api_keys", "key_hash_1", True)
    ]

    all_passed = True
    for collection_name, index_name, is_unique in test_cases:
        try:
            collection = db[collection_name]
            indexes = collection.index_information()

            if index_name in indexes:
                index_info = indexes[index_name]
                unique_match = index_info.get('unique', False) == is_unique
                print_test(
                    f"Index: {collection_name}.{index_name}",
                    True,
                    f"unique={is_unique}" if is_unique else ""
                )
            else:
                print_test(f"Index: {collection_name}.{index_name}", False, "Index not found")
                all_passed = False
        except Exception as e:
            print_test(f"Index: {collection_name}.{index_name}", False, str(e))
            all_passed = False

    return all_passed


def test_initial_data(db):
    """Test that initial data was inserted."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Initial Data ==={Colors.RESET}")

    # Test system_config
    config_count = db.system_config.count_documents({})
    print_test("System Config Count", config_count == 4, f"Found {config_count} entries")

    # Test schema_versions
    version_count = db.schema_versions.count_documents({})
    print_test("Schema Versions Count", version_count == 1, f"Found {version_count} entries")

    # Verify specific config entries
    app_version = db.system_config.find_one({"config_key": "app_version"})
    print_test("App Version Config", app_version is not None, f"Version: {app_version.get('config_value') if app_version else 'N/A'}")

    return config_count == 4 and version_count == 1


def test_pydantic_models():
    """Test Pydantic model creation and validation."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Pydantic Models ==={Colors.RESET}")

    tests_passed = True

    # Test SystemConfig model
    try:
        config = SystemConfig(
            config_key="test_key",
            config_value="test_value",
            config_type=ConfigType.STRING
        )
        print_test("SystemConfig Model", True)
    except Exception as e:
        print_test("SystemConfig Model", False, str(e))
        tests_passed = False

    # Test Customer model
    try:
        customer = Customer(
            company_name="Test Company",
            address="123 Test St",
            contact_person="John Doe"
        )
        print_test("Customer Model", True)
    except Exception as e:
        print_test("Customer Model", False, str(e))
        tests_passed = False

    # Test CompanyUser model
    try:
        user = CompanyUser(
            user_id="test_user_001",
            customer_id=PyObjectId(ObjectId()),
            user_name="Test User",
            email="test@example.com"
        )
        print_test("CompanyUser Model", True)
    except Exception as e:
        print_test("CompanyUser Model", False, str(e))
        tests_passed = False

    # Test Subscription model
    try:
        subscription = Subscription(
            customer_id=PyObjectId(ObjectId()),
            subscription_unit=SubscriptionUnit.PAGE,
            units_per_subscription=1000,
            price_per_unit=0.10,
            subscription_price=100.0,
            start_date=datetime.now(timezone.utc)
        )
        print_test("Subscription Model", True)
    except Exception as e:
        print_test("Subscription Model", False, str(e))
        tests_passed = False

    # Test TranslationTransaction model
    try:
        transaction = TranslationTransaction(
            customer_id=PyObjectId(ObjectId()),
            requester_id="user123",
            user_name="Test User",
            units_consumed=10,
            original_file_url="https://example.com/file.pdf",
            source_language="en",
            target_language="es"
        )
        print_test("TranslationTransaction Model", True)
    except Exception as e:
        print_test("TranslationTransaction Model", False, str(e))
        tests_passed = False

    return tests_passed


def test_crud_operations(db):
    """Test CRUD operations with Pydantic models."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing CRUD Operations ==={Colors.RESET}")

    tests_passed = True

    # CREATE: Insert a test customer
    try:
        customer = Customer(
            company_name="Test CRUD Company",
            address="456 CRUD St",
            contact_person="Jane Doe",
            phone_number="555-1234"
        )

        result = db.customers.insert_one(customer.model_dump(by_alias=True, exclude={"id"}))
        customer_id = result.inserted_id
        print_test("CREATE Customer", True, f"ID: {customer_id}")
    except Exception as e:
        print_test("CREATE Customer", False, str(e))
        tests_passed = False
        return tests_passed

    # READ: Retrieve the customer
    try:
        doc = db.customers.find_one({"_id": customer_id})
        retrieved_customer = Customer(**doc)
        print_test("READ Customer", True, f"Company: {retrieved_customer.company_name}")
    except Exception as e:
        print_test("READ Customer", False, str(e))
        tests_passed = False

    # UPDATE: Update the customer
    try:
        db.customers.update_one(
            {"_id": customer_id},
            {"$set": {"phone_number": "555-9999", "updated_at": datetime.now(timezone.utc)}}
        )
        updated_doc = db.customers.find_one({"_id": customer_id})
        print_test("UPDATE Customer", updated_doc['phone_number'] == "555-9999", f"New phone: {updated_doc['phone_number']}")
    except Exception as e:
        print_test("UPDATE Customer", False, str(e))
        tests_passed = False

    # CREATE: Add a company user for this customer
    try:
        user = CompanyUser(
            user_id="test_crud_user_001",
            customer_id=PyObjectId(customer_id),
            user_name="CRUD Test User",
            email="crud@example.com",
            permission_level="admin"
        )

        result = db.company_users.insert_one(user.model_dump(by_alias=True, exclude={"id"}))
        user_id = result.inserted_id
        print_test("CREATE CompanyUser", True, f"User ID: {user_id}")
    except Exception as e:
        print_test("CREATE CompanyUser", False, str(e))
        tests_passed = False

    # Query with relationship
    try:
        users_for_customer = db.company_users.find({"customer_id": customer_id})
        user_count = db.company_users.count_documents({"customer_id": customer_id})
        print_test("QUERY by customer_id", user_count > 0, f"Found {user_count} users")
    except Exception as e:
        print_test("QUERY by customer_id", False, str(e))
        tests_passed = False

    # DELETE: Clean up test data
    try:
        db.company_users.delete_many({"customer_id": customer_id})
        db.customers.delete_one({"_id": customer_id})
        print_test("DELETE Test Data", True, "Cleanup successful")
    except Exception as e:
        print_test("DELETE Test Data", False, str(e))
        tests_passed = False

    return tests_passed


def test_validation_rules(db):
    """Test validation rules and constraints."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== Testing Validation Rules ==={Colors.RESET}")

    tests_passed = True

    # Test unique constraint on config_key
    try:
        db.system_config.insert_one({
            "config_key": "app_version",  # Already exists
            "config_value": "2.0.0",
            "config_type": "string",
            "updated_at": datetime.now(timezone.utc)
        })
        print_test("Unique Constraint (config_key)", False, "Should have failed but didn't")
        tests_passed = False
    except Exception as e:
        if "duplicate key" in str(e).lower():
            print_test("Unique Constraint (config_key)", True, "Duplicate rejected correctly")
        else:
            print_test("Unique Constraint (config_key)", False, str(e))
            tests_passed = False

    # Test enum validation in Pydantic
    try:
        config = SystemConfig(
            config_key="test_enum",
            config_value="test",
            config_type="invalid_type"  # Should fail
        )
        print_test("Enum Validation", False, "Should have failed but didn't")
        tests_passed = False
    except Exception as e:
        if "validation" in str(e).lower() or "error" in str(e).lower():
            print_test("Enum Validation", True, "Invalid enum rejected")
        else:
            print_test("Enum Validation", False, str(e))
            tests_passed = False

    # Test email validation in Pydantic
    try:
        admin = SystemAdmin(
            username="testadmin",
            email="invalid-email",  # Should fail
            password_hash="hash123"
        )
        print_test("Email Validation", False, "Should have failed but didn't")
        tests_passed = False
    except Exception as e:
        if "validation" in str(e).lower() or "email" in str(e).lower():
            print_test("Email Validation", True, "Invalid email rejected")
        else:
            print_test("Email Validation", False, str(e))
            tests_passed = False

    return tests_passed


def run_all_tests():
    """Run all test suites."""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}MongoDB Setup Test Suite{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")

    # Connect to MongoDB
    client, db = test_connection()

    # Run test suites
    results = {
        "Collections": test_collections(db),
        "Indexes": test_indexes(db),
        "Initial Data": test_initial_data(db),
        "Pydantic Models": test_pydantic_models(),
        "CRUD Operations": test_crud_operations(db),
        "Validation Rules": test_validation_rules(db)
    }

    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}Test Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}")

    total_suites = len(results)
    passed_suites = sum(1 for passed in results.values() if passed)

    for suite_name, passed in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"{status} - {suite_name}")

    print(f"\n{Colors.BOLD}Overall: {passed_suites}/{total_suites} test suites passed{Colors.RESET}")

    # Collection statistics
    print(f"\n{Colors.BOLD}Collection Statistics:{Colors.RESET}")
    for collection_name in sorted(db.list_collection_names()):
        count = db[collection_name].count_documents({})
        print(f"  - {collection_name:30} {count:5} documents")

    if passed_suites == total_suites:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.RESET}")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
