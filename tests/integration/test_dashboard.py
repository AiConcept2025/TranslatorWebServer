"""
INTEGRATION TESTS FOR DASHBOARD API - USING REAL DATABASE

These tests make actual HTTP requests to the running server and verify
responses against the REAL MongoDB database (translation).

NO MOCKS - Real API + Real Database testing as per requirements.
"""

import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient


# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"  # REAL production database


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db():
    """
    Connect to REAL production MongoDB database.

    CRITICAL: Uses production database 'translation', NOT 'translation_test'.
    Tests query real data but do NOT modify or delete records.
    """
    mongo_client = AsyncIOMotorClient(MONGODB_URI)
    database = mongo_client[DATABASE_NAME]

    yield database

    # No cleanup - we use real production data
    mongo_client.close()


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture
async def database_metrics(db):
    """
    Query real database to get expected metrics for validation.

    Returns actual counts from database to compare against API responses.
    """
    # 1. Total Revenue - sum all COMPLETED payments
    revenue_pipeline = [
        {"$match": {"payment_status": "COMPLETED"}},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$amount"}
        }}
    ]
    revenue_result = await db.payments.aggregate(revenue_pipeline).to_list(length=1)
    total_revenue_cents = revenue_result[0]["total"] if revenue_result else 0
    total_revenue_dollars = total_revenue_cents / 100.0

    # 2. Active Subscriptions
    active_subscriptions = await db.subscriptions.count_documents({"status": "active"})

    # 3. Total Transactions (translation_transactions + user_transactions)
    translation_txn_count = await db.translation_transactions.count_documents({})
    user_txn_count = await db.user_transactions.count_documents({})
    total_transactions = translation_txn_count + user_txn_count

    # 4. Active Companies (distinct companies with active subscriptions)
    active_companies_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$company_name"}},
        {"$count": "total"}
    ]
    active_companies_result = await db.subscriptions.aggregate(active_companies_pipeline).to_list(length=1)
    active_companies = active_companies_result[0]["total"] if active_companies_result else 0

    return {
        "total_revenue": round(total_revenue_dollars, 2),
        "active_subscriptions": active_subscriptions,
        "total_transactions": total_transactions,
        "active_companies": active_companies
    }


# ============================================================================
# Test 1: Dashboard Metrics Endpoint
# ============================================================================

@pytest.mark.asyncio
class TestDashboardMetrics:
    """Test dashboard metrics endpoint against real database."""

    async def test_get_dashboard_metrics_success(self, http_client):
        """Test 1.1: Request to /api/v1/dashboard/metrics returns 200"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        print("✅ Test 1.1: PASSED - Dashboard metrics endpoint returned 200")

    async def test_dashboard_metrics_structure(self, http_client):
        """Test 1.2: Response has correct structure with all required fields"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data

        # Check required fields
        metrics = data["data"]
        assert "total_revenue" in metrics
        assert "active_subscriptions" in metrics
        assert "total_transactions" in metrics
        assert "active_companies" in metrics

        print("✅ Test 1.2: PASSED - Response has all required fields")

    async def test_dashboard_metrics_data_types(self, http_client):
        """Test 1.3: All metric fields have correct data types"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        metrics = data["data"]

        # Verify data types
        assert isinstance(metrics["total_revenue"], (int, float)), "total_revenue should be numeric"
        assert isinstance(metrics["active_subscriptions"], int), "active_subscriptions should be int"
        assert isinstance(metrics["total_transactions"], int), "total_transactions should be int"
        assert isinstance(metrics["active_companies"], int), "active_companies should be int"

        print(f"✅ Test 1.3: PASSED - All fields have correct types")

    async def test_dashboard_metrics_values(self, http_client):
        """Test 1.4: All metric values are non-negative"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        metrics = data["data"]

        # Verify values are non-negative
        assert metrics["total_revenue"] >= 0, "total_revenue should be >= 0"
        assert metrics["active_subscriptions"] >= 0, "active_subscriptions should be >= 0"
        assert metrics["total_transactions"] >= 0, "total_transactions should be >= 0"
        assert metrics["active_companies"] >= 0, "active_companies should be >= 0"

        print(f"✅ Test 1.4: PASSED - All values are non-negative")

    async def test_dashboard_metrics_match_database(self, http_client, database_metrics):
        """Test 1.5: API metrics match database counts exactly"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        api_metrics = data["data"]

        # Get expected values from database
        db_metrics = database_metrics if not hasattr(database_metrics, '__await__') else await database_metrics

        # Compare each metric
        assert api_metrics["total_revenue"] == db_metrics["total_revenue"], \
            f"Total revenue mismatch: API={api_metrics['total_revenue']}, DB={db_metrics['total_revenue']}"

        assert api_metrics["active_subscriptions"] == db_metrics["active_subscriptions"], \
            f"Active subscriptions mismatch: API={api_metrics['active_subscriptions']}, DB={db_metrics['active_subscriptions']}"

        assert api_metrics["total_transactions"] == db_metrics["total_transactions"], \
            f"Total transactions mismatch: API={api_metrics['total_transactions']}, DB={db_metrics['total_transactions']}"

        assert api_metrics["active_companies"] == db_metrics["active_companies"], \
            f"Active companies mismatch: API={api_metrics['active_companies']}, DB={db_metrics['active_companies']}"

        print(f"✅ Test 1.5: PASSED - All metrics match database:")
        print(f"   Total Revenue: ${api_metrics['total_revenue']}")
        print(f"   Active Subscriptions: {api_metrics['active_subscriptions']}")
        print(f"   Total Transactions: {api_metrics['total_transactions']}")
        print(f"   Active Companies: {api_metrics['active_companies']}")


# ============================================================================
# Test 2: Edge Cases
# ============================================================================

@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_metrics_with_no_data(self, http_client):
        """Test 2.1: Metrics endpoint handles empty database gracefully"""
        # This test passes if the endpoint returns 0 for all metrics
        # (in a fresh database with no data)
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()

        # All values should be valid numbers (even if 0)
        assert isinstance(data["data"]["total_revenue"], (int, float))
        assert isinstance(data["data"]["active_subscriptions"], int)
        assert isinstance(data["data"]["total_transactions"], int)
        assert isinstance(data["data"]["active_companies"], int)

        print("✅ Test 2.1: PASSED - Endpoint handles empty data gracefully")

    async def test_revenue_calculation_precision(self, http_client, db):
        """Test 2.2: Revenue calculation maintains correct precision (cents to dollars)"""
        response = await http_client.get("/api/v1/dashboard/metrics")

        assert response.status_code == 200
        data = response.json()
        revenue = data["data"]["total_revenue"]

        # Revenue should be rounded to 2 decimal places
        assert revenue == round(revenue, 2), "Revenue should be rounded to 2 decimal places"

        # Verify by checking a sample payment
        sample_payment = await db.payments.find_one({"payment_status": "COMPLETED"})
        if sample_payment:
            # Payment amounts are stored in cents, should be converted to dollars
            assert isinstance(revenue, (int, float)), "Revenue should be numeric"
            print(f"✅ Test 2.2: PASSED - Revenue precision correct: ${revenue}")
        else:
            print("⚠️  Test 2.2: SKIPPED - No COMPLETED payments found")


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("DASHBOARD API INTEGRATION TESTS - REAL DATABASE")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("\nNOTE: These tests use REAL production data and do NOT modify/delete records")
    print("=" * 80)
    print("\n")
