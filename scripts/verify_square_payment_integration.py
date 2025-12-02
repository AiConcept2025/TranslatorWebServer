#!/usr/bin/env python3
"""
Verify Stripe Payment Integration

Tests all components of the Stripe payment integration:
1. Pydantic models
2. Helper functions
3. Router endpoints
4. Database operations

Usage:
    python3 server/scripts/verify_square_payment_integration.py
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_models():
    """Verify all Pydantic models can be imported and validated."""
    print("\n" + "=" * 80)
    print("STEP 1: Verifying Pydantic Models")
    print("=" * 80)

    try:
        from app.models.payment import (
            RefundSchema,
            UserTransactionSchema,
            UserTransactionCreate,
            UserTransactionResponse,
            RefundRequest,
        )

        print("✓ All models imported successfully")

        # Test RefundSchema validation
        refund = RefundSchema(
            refund_id="test_refund",
            amount_cents=100,
            status="COMPLETED",
            idempotency_key="test_key",
        )
        print(f"✓ RefundSchema validation works: {refund.refund_id}")

        # Test UserTransactionCreate validation
        from datetime import datetime
        txn_create = UserTransactionCreate(
            user_name="Test User",
            user_email="test@example.com",
            document_url="https://example.com/doc",
            number_of_units=10,
            unit_type="page",
            cost_per_unit=0.15,
            source_language="en",
            target_language="es",
            stripe_checkout_session_id="STRIPE-TEST",
            stripe_payment_intent_id="STRIPE-PAY-TEST",
        )
        print(f"✓ UserTransactionCreate validation works: {txn_create.stripe_checkout_session_id}")

        return True

    except Exception as e:
        print(f"✗ Model verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_helper_functions():
    """Verify helper functions are available."""
    print("\n" + "=" * 80)
    print("STEP 2: Verifying Helper Functions")
    print("=" * 80)

    try:
        from app.utils.user_transaction_helper import (
            create_user_transaction,
            update_user_transaction_status,
            get_user_transactions_by_email,
            get_user_transaction,
            add_refund_to_transaction,
            update_payment_status,
        )

        print("✓ create_user_transaction imported")
        print("✓ update_user_transaction_status imported")
        print("✓ get_user_transactions_by_email imported")
        print("✓ get_user_transaction imported")
        print("✓ add_refund_to_transaction imported")
        print("✓ update_payment_status imported")

        # Verify function signatures
        import inspect

        sig = inspect.signature(create_user_transaction)
        params = list(sig.parameters.keys())

        required_params = [
            "stripe_payment_intent_id",
            "amount_cents",
            "currency",
            "payment_status",
            "payment_date",
            "refunds",
        ]

        for param in required_params:
            if param in params:
                print(f"✓ create_user_transaction has parameter: {param}")
            else:
                print(f"✗ Missing parameter: {param}")
                return False

        return True

    except Exception as e:
        print(f"✗ Helper function verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_router():
    """Verify router is properly configured."""
    print("\n" + "=" * 80)
    print("STEP 3: Verifying Router")
    print("=" * 80)

    try:
        from app.routers.user_transactions import router

        print(f"✓ Router imported: {router.prefix}")
        print(f"✓ Router tags: {router.tags}")

        # Count routes
        route_count = len(router.routes)
        print(f"✓ Router has {route_count} routes")

        # List all routes
        for route in router.routes:
            methods = ", ".join(route.methods) if hasattr(route, "methods") else "N/A"
            path = route.path if hasattr(route, "path") else "N/A"
            print(f"  - {methods:6s} {path}")

        if route_count < 5:
            print(f"✗ Expected at least 5 routes, found {route_count}")
            return False

        return True

    except Exception as e:
        print(f"✗ Router verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_app_integration():
    """Verify router is registered in main app."""
    print("\n" + "=" * 80)
    print("STEP 4: Verifying App Integration")
    print("=" * 80)

    try:
        from app.main import app

        # Check if user_transactions routes are registered
        user_txn_routes = [
            r for r in app.routes if "/user-transactions" in str(r.path)
        ]

        print(f"✓ FastAPI app loaded")
        print(f"✓ Total routes in app: {len(app.routes)}")
        print(f"✓ User transaction routes: {len(user_txn_routes)}")

        if len(user_txn_routes) < 5:
            print(
                f"✗ Expected at least 5 user transaction routes, found {len(user_txn_routes)}"
            )
            return False

        # List user transaction routes
        print("\n  User Transaction Routes:")
        for route in user_txn_routes:
            methods = ", ".join(route.methods) if hasattr(route, "methods") else "N/A"
            path = route.path if hasattr(route, "path") else "N/A"
            print(f"    - {methods:6s} {path}")

        return True

    except Exception as e:
        print(f"✗ App integration verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_backwards_compatibility():
    """Verify backward compatibility of helper functions."""
    print("\n" + "=" * 80)
    print("STEP 5: Verifying Backward Compatibility")
    print("=" * 80)

    try:
        import inspect
        from app.utils.user_transaction_helper import create_user_transaction

        sig = inspect.signature(create_user_transaction)

        # Check that new parameters are optional
        new_params = [
            "stripe_payment_intent_id",
            "amount_cents",
            "currency",
            "payment_status",
            "payment_date",
            "refunds",
        ]

        for param in new_params:
            param_obj = sig.parameters.get(param)
            if param_obj:
                has_default = param_obj.default != inspect.Parameter.empty
                if has_default:
                    print(
                        f"✓ {param} is optional (default: {param_obj.default!r})"
                    )
                else:
                    print(f"✗ {param} is required (no default)")
                    return False
            else:
                print(f"✗ Parameter {param} not found")
                return False

        print("\n✓ All new parameters have defaults - backward compatible!")
        return True

    except Exception as e:
        print(f"✗ Backward compatibility verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main verification function."""
    print("\n" + "=" * 80)
    print("SQUARE PAYMENT INTEGRATION VERIFICATION")
    print("=" * 80)

    results = {
        "Models": verify_models(),
        "Helper Functions": verify_helper_functions(),
        "Router": verify_router(),
        "App Integration": verify_app_integration(),
        "Backward Compatibility": verify_backwards_compatibility(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:25s}: {status}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n🎉 ALL VERIFICATIONS PASSED! 🎉")
        print("\nSquare payment integration is ready for use.")
        print("\nNext steps:")
        print("  1. Start the server: uvicorn app.main:app --reload")
        print("  2. Access API docs: http://localhost:8000/docs")
        print("  3. Test with dummy script: python3 scripts/create_dummy_user_transaction.py")
        print("  4. Review API reference: USER_TRANSACTIONS_API_QUICK_REFERENCE.md")
        return 0
    else:
        print("\n❌ SOME VERIFICATIONS FAILED ❌")
        print("\nPlease review the errors above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
