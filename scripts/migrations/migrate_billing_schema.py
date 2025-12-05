#!/usr/bin/env python3
"""
Migration Script: Billing Schema Enhancement

This script enhances the subscription billing schema with:
1. Flexible billing frequencies (monthly/quarterly/yearly)
2. Quarterly invoice generation support with line items
3. Payment-to-invoice linkage

Database: translation (production) and translation_test (test)
Collections: subscriptions, invoices, payments

CRITICAL: Preserves all existing data - ONLY ADDS new fields

Changes:
- subscriptions: +billing_frequency, +payment_terms_days, +usage_periods[].period_number
- invoices: +billing_period, +line_items, +subtotal, +amount_paid, +stripe_invoice_id
- payments: +invoice_id, +subscription_id, +total_refunded

Author: Claude Code
Date: 2025-12-02
"""

import sys
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import (
        ConnectionFailure,
        DuplicateKeyError,
        OperationFailure,
        ServerSelectionTimeoutError
    )
    from bson import ObjectId
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    print("\nPlease install required packages:")
    print("  pip install pymongo")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BillingSchemaEnhancementMigration:
    """Handles billing schema migration with rollback support."""

    # MongoDB connection details
    MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/{database}?authSource=translation"

    def __init__(self, database_name: str = "translation", dry_run: bool = False):
        """
        Initialize migration.

        Args:
            database_name: Database name ('translation' or 'translation_test')
            dry_run: If True, preview changes without applying
        """
        self.database_name = database_name
        self.dry_run = dry_run
        self.client: Optional[MongoClient] = None
        self.db = None
        self.migration_log: Dict[str, Any] = {
            "started_at": datetime.now(timezone.utc),
            "steps_completed": [],
            "steps_failed": [],
            "rollback_needed": False,
            "dry_run": dry_run
        }

    def connect(self) -> bool:
        """
        Connect to MongoDB.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("BILLING SCHEMA ENHANCEMENT MIGRATION")
            logger.info("=" * 80)
            logger.info(f"Target database: {self.database_name}")
            if self.dry_run:
                logger.info("Mode: DRY RUN (no changes will be made)")
            else:
                logger.info("Mode: LIVE (changes will be applied)")
            logger.info("")

            logger.info("Connecting to MongoDB...")

            # Create synchronous MongoDB client
            uri = self.MONGODB_URI.format(database=self.database_name)
            self.client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000
            )

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.db = self.client[self.database_name]

            logger.info(f"✓ Successfully connected to MongoDB database: {self.database_name}")
            return True

        except ConnectionFailure as e:
            logger.error(f"✗ Failed to connect to MongoDB: {e}")
            return False
        except ServerSelectionTimeoutError as e:
            logger.error(f"✗ MongoDB server selection timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error during connection: {e}", exc_info=True)
            return False

    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    def check_preconditions(self) -> bool:
        """
        Check if migration can proceed safely.

        Returns:
            bool: True if preconditions met, False otherwise
        """
        logger.info("")
        logger.info("STEP 0: Checking preconditions...")
        logger.info("-" * 80)

        try:
            # Check collections exist
            collections_needed = ['subscriptions', 'invoices', 'payments']
            existing_collections = self.db.list_collection_names()

            for coll_name in collections_needed:
                if coll_name not in existing_collections:
                    logger.error(f"✗ Collection '{coll_name}' does not exist!")
                    return False
                logger.info(f"✓ Collection '{coll_name}' exists")

            # Count documents
            sub_count = self.db.subscriptions.count_documents({})
            inv_count = self.db.invoices.count_documents({})
            pmt_count = self.db.payments.count_documents({})

            logger.info(f"✓ Found {sub_count} subscriptions")
            logger.info(f"✓ Found {inv_count} invoices")
            logger.info(f"✓ Found {pmt_count} payments")

            # Check if migration already run (check for new fields)
            sub_with_billing_freq = self.db.subscriptions.count_documents({
                "billing_frequency": {"$exists": True}
            })

            if sub_with_billing_freq > 0:
                logger.warning(f"⚠ {sub_with_billing_freq} subscriptions already have billing_frequency field")
                logger.warning("  Migration may have been run previously")

            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Precondition check failed: {e}", exc_info=True)
            return False

    def step1_migrate_subscriptions(self) -> bool:
        """
        Add billing_frequency, payment_terms_days to subscriptions.
        Calculate and add period_number to each usage_period.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 1: Migrate subscriptions")
        logger.info("-" * 80)

        try:
            collection = self.db.subscriptions

            # Find all subscriptions without new fields
            query = {
                "$or": [
                    {"billing_frequency": {"$exists": False}},
                    {"payment_terms_days": {"$exists": False}}
                ]
            }

            subscriptions = list(collection.find(query))
            logger.info(f"Found {len(subscriptions)} subscriptions to migrate")

            if self.dry_run:
                logger.info("[DRY RUN] Would update subscriptions with:")
                logger.info("  - billing_frequency: 'monthly'")
                logger.info("  - payment_terms_days: 30")
                logger.info("  - usage_periods[].period_number: 1-12 (auto-calculated)")
                self.migration_log["steps_completed"].append("step1_subscriptions (dry_run)")
                logger.info("")
                return True

            updated_count = 0
            for sub in subscriptions:
                # Calculate period_number for each usage_period
                usage_periods = sub.get("usage_periods", [])
                for idx, period in enumerate(usage_periods):
                    if "period_number" not in period:
                        period["period_number"] = idx + 1  # 1-indexed

                # Update subscription
                result = collection.update_one(
                    {"_id": sub["_id"]},
                    {
                        "$set": {
                            "billing_frequency": "monthly",
                            "payment_terms_days": 30,
                            "usage_periods": usage_periods,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                if result.modified_count > 0:
                    updated_count += 1

            logger.info(f"✓ Updated {updated_count} subscriptions")
            self.migration_log["steps_completed"].append(f"step1_subscriptions: {updated_count} updated")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Step 1 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step1_subscriptions", str(e)))
            return False

    def step2_migrate_invoices(self) -> bool:
        """
        Add billing_period, line_items, subtotal, amount_paid to invoices.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 2: Migrate invoices")
        logger.info("-" * 80)

        try:
            collection = self.db.invoices

            # Find all invoices without new fields
            query = {
                "$or": [
                    {"line_items": {"$exists": False}},
                    {"subtotal": {"$exists": False}}
                ]
            }

            invoices = list(collection.find(query))
            logger.info(f"Found {len(invoices)} invoices to migrate")

            if self.dry_run:
                logger.info("[DRY RUN] Would update invoices with:")
                logger.info("  - billing_period: null (for existing invoices)")
                logger.info("  - line_items: [] (empty array)")
                logger.info("  - subtotal: calculated (total_amount - tax_amount)")
                logger.info("  - amount_paid: 0.0")
                logger.info("  - stripe_invoice_id: null")
                self.migration_log["steps_completed"].append("step2_invoices (dry_run)")
                logger.info("")
                return True

            updated_count = 0
            for inv in invoices:
                # Calculate subtotal (total_amount - tax_amount)
                # Handle Decimal128 types from MongoDB
                total_amount = inv.get("total_amount", 0.0)
                tax_amount = inv.get("tax_amount", 0.0)

                # Convert Decimal128 to float if needed
                if hasattr(total_amount, 'to_decimal'):
                    total_amount = float(total_amount.to_decimal())
                if hasattr(tax_amount, 'to_decimal'):
                    tax_amount = float(tax_amount.to_decimal())

                subtotal = total_amount - tax_amount

                # Create default line item for existing invoices (if total > 0)
                line_items = []
                if total_amount > 0:
                    line_items.append({
                        "description": "Legacy invoice line item (migrated)",
                        "period_numbers": [1],
                        "quantity": 1,
                        "unit_price": subtotal,
                        "amount": subtotal
                    })

                # Update invoice
                result = collection.update_one(
                    {"_id": inv["_id"]},
                    {
                        "$set": {
                            "billing_period": None,
                            "line_items": line_items,
                            "subtotal": subtotal,
                            "amount_paid": 0.0,
                            "stripe_invoice_id": None,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                if result.modified_count > 0:
                    updated_count += 1

            logger.info(f"✓ Updated {updated_count} invoices")
            self.migration_log["steps_completed"].append(f"step2_invoices: {updated_count} updated")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Step 2 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step2_invoices", str(e)))
            return False

    def step3_migrate_payments(self) -> bool:
        """
        Add invoice_id, subscription_id, total_refunded to payments.
        Link payments to invoices via stripe_invoice_id matching.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 3: Migrate payments")
        logger.info("-" * 80)

        try:
            collection = self.db.payments

            # Find all payments without new fields
            query = {
                "$or": [
                    {"total_refunded": {"$exists": False}},
                    {"subscription_id": {"$exists": False}}
                ]
            }

            payments = list(collection.find(query))
            logger.info(f"Found {len(payments)} payments to migrate")

            if self.dry_run:
                logger.info("[DRY RUN] Would update payments with:")
                logger.info("  - invoice_id: linked via stripe_invoice_id (or null)")
                logger.info("  - subscription_id: linked via company_name (or null)")
                logger.info("  - total_refunded: calculated from refunds array")
                self.migration_log["steps_completed"].append("step3_payments (dry_run)")
                logger.info("")
                return True

            updated_count = 0
            linked_invoices = 0
            linked_subscriptions = 0

            for pmt in payments:
                # Calculate total_refunded from refunds array
                refunds = pmt.get("refunds", [])
                total_refunded = sum(r.get("amount", 0) / 100.0 for r in refunds)

                # Try to link to invoice via stripe_invoice_id
                invoice_id = None
                stripe_invoice_id = pmt.get("stripe_invoice_id")
                if stripe_invoice_id:
                    invoice = self.db.invoices.find_one({
                        "stripe_invoice_id": stripe_invoice_id
                    })
                    if invoice:
                        invoice_id = str(invoice["_id"])
                        linked_invoices += 1

                # Try to link to subscription via company_name
                subscription_id = None
                company_name = pmt.get("company_name")
                if company_name:
                    subscription = self.db.subscriptions.find_one({
                        "company_name": company_name,
                        "status": {"$in": ["active", "inactive"]}
                    })
                    if subscription:
                        subscription_id = str(subscription["_id"])
                        linked_subscriptions += 1

                # Update payment
                result = collection.update_one(
                    {"_id": pmt["_id"]},
                    {
                        "$set": {
                            "invoice_id": invoice_id,
                            "subscription_id": subscription_id,
                            "total_refunded": total_refunded,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                if result.modified_count > 0:
                    updated_count += 1

            logger.info(f"✓ Updated {updated_count} payments")
            logger.info(f"  - Linked to invoices: {linked_invoices}")
            logger.info(f"  - Linked to subscriptions: {linked_subscriptions}")
            self.migration_log["steps_completed"].append(f"step3_payments: {updated_count} updated")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Step 3 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step3_payments", str(e)))
            return False

    def step4_create_indexes(self) -> bool:
        """
        Create indexes for new fields.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 4: Create indexes")
        logger.info("-" * 80)

        if self.dry_run:
            logger.info("[DRY RUN] Would create indexes:")
            logger.info("  - subscriptions.billing_frequency")
            logger.info("  - invoices.stripe_invoice_id (unique, sparse)")
            logger.info("  - invoices.amount_paid")
            logger.info("  - payments.invoice_id (sparse)")
            logger.info("  - payments.subscription_id (sparse)")
            self.migration_log["steps_completed"].append("step4_indexes (dry_run)")
            logger.info("")
            return True

        try:
            # Subscriptions indexes
            try:
                self.db.subscriptions.create_index(
                    [("billing_frequency", ASCENDING)],
                    name="billing_frequency_idx",
                    background=True
                )
                logger.info("✓ Created index: subscriptions.billing_frequency_idx")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠ Index billing_frequency_idx already exists")
                else:
                    raise

            # Invoices indexes
            try:
                self.db.invoices.create_index(
                    [("stripe_invoice_id", ASCENDING)],
                    unique=True,
                    sparse=True,
                    name="stripe_invoice_id_unique",
                    background=True
                )
                logger.info("✓ Created index: invoices.stripe_invoice_id_unique")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠ Index stripe_invoice_id_unique already exists")
                else:
                    raise

            try:
                self.db.invoices.create_index(
                    [("amount_paid", ASCENDING)],
                    name="amount_paid_idx",
                    background=True
                )
                logger.info("✓ Created index: invoices.amount_paid_idx")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠ Index amount_paid_idx already exists")
                else:
                    raise

            # Payments indexes
            try:
                self.db.payments.create_index(
                    [("invoice_id", ASCENDING)],
                    sparse=True,
                    name="invoice_id_idx",
                    background=True
                )
                logger.info("✓ Created index: payments.invoice_id_idx")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠ Index invoice_id_idx already exists")
                else:
                    raise

            try:
                self.db.payments.create_index(
                    [("subscription_id", ASCENDING)],
                    sparse=True,
                    name="subscription_id_idx",
                    background=True
                )
                logger.info("✓ Created index: payments.subscription_id_idx")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "IndexKeySpecsConflict" in str(e):
                    logger.warning("⚠ Index subscription_id_idx already exists")
                else:
                    raise

            logger.info("✓ All indexes created successfully")
            self.migration_log["steps_completed"].append("step4_indexes")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Step 4 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step4_indexes", str(e)))
            return False

    def verify_migration(self) -> bool:
        """
        Verify migration completed successfully.

        Returns:
            bool: True if verification passed, False otherwise
        """
        logger.info("STEP 5: Verify migration")
        logger.info("-" * 80)

        try:
            errors = []

            # Verify subscriptions
            sub_with_new_fields = self.db.subscriptions.count_documents({
                "billing_frequency": {"$exists": True},
                "payment_terms_days": {"$exists": True}
            })
            total_subs = self.db.subscriptions.count_documents({})

            if sub_with_new_fields != total_subs:
                errors.append(f"Subscriptions: Only {sub_with_new_fields}/{total_subs} have new fields")
            else:
                logger.info(f"✓ All {total_subs} subscriptions migrated")

            # Verify invoices
            inv_with_new_fields = self.db.invoices.count_documents({
                "line_items": {"$exists": True},
                "subtotal": {"$exists": True}
            })
            total_invs = self.db.invoices.count_documents({})

            if inv_with_new_fields != total_invs:
                errors.append(f"Invoices: Only {inv_with_new_fields}/{total_invs} have new fields")
            else:
                logger.info(f"✓ All {total_invs} invoices migrated")

            # Verify payments
            pmt_with_new_fields = self.db.payments.count_documents({
                "total_refunded": {"$exists": True}
            })
            total_pmts = self.db.payments.count_documents({})

            if pmt_with_new_fields != total_pmts:
                errors.append(f"Payments: Only {pmt_with_new_fields}/{total_pmts} have new fields")
            else:
                logger.info(f"✓ All {total_pmts} payments migrated")

            # Verify indexes exist
            sub_indexes = [idx.get('name') for idx in self.db.subscriptions.list_indexes()]
            inv_indexes = [idx.get('name') for idx in self.db.invoices.list_indexes()]
            pmt_indexes = [idx.get('name') for idx in self.db.payments.list_indexes()]

            if "billing_frequency_idx" not in sub_indexes:
                errors.append("Missing index: subscriptions.billing_frequency_idx")
            if "stripe_invoice_id_unique" not in inv_indexes:
                errors.append("Missing index: invoices.stripe_invoice_id_unique")
            if "invoice_id_idx" not in pmt_indexes:
                errors.append("Missing index: payments.invoice_id_idx")

            if not errors:
                logger.info("✓ All indexes created")

            if errors:
                for error in errors:
                    logger.error(f"✗ {error}")
                logger.info("")
                return False

            logger.info("✓ Migration verification PASSED")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Verification failed: {e}", exc_info=True)
            return False

    def rollback(self) -> bool:
        """
        Rollback migration (remove new fields).

        Returns:
            bool: True if rollback successful, False otherwise
        """
        logger.warning("=" * 80)
        logger.warning("ROLLBACK: Removing new fields...")
        logger.warning("=" * 80)

        try:
            # Remove new fields from subscriptions
            result_subs = self.db.subscriptions.update_many(
                {},
                {
                    "$unset": {
                        "billing_frequency": "",
                        "payment_terms_days": ""
                    }
                }
            )
            logger.info(f"✓ Removed billing fields from {result_subs.modified_count} subscriptions")

            # Remove period_number from usage_periods
            subscriptions = list(self.db.subscriptions.find({}))
            for sub in subscriptions:
                usage_periods = sub.get("usage_periods", [])
                for period in usage_periods:
                    period.pop("period_number", None)
                self.db.subscriptions.update_one(
                    {"_id": sub["_id"]},
                    {"$set": {"usage_periods": usage_periods}}
                )
            logger.info(f"✓ Removed period_number from usage_periods")

            # Remove new fields from invoices
            result_invs = self.db.invoices.update_many(
                {},
                {
                    "$unset": {
                        "billing_period": "",
                        "line_items": "",
                        "subtotal": "",
                        "amount_paid": "",
                        "stripe_invoice_id": ""
                    }
                }
            )
            logger.info(f"✓ Removed invoice fields from {result_invs.modified_count} invoices")

            # Remove new fields from payments
            result_pmts = self.db.payments.update_many(
                {},
                {
                    "$unset": {
                        "invoice_id": "",
                        "subscription_id": "",
                        "total_refunded": ""
                    }
                }
            )
            logger.info(f"✓ Removed payment fields from {result_pmts.modified_count} payments")

            # Drop new indexes
            try:
                self.db.subscriptions.drop_index("billing_frequency_idx")
                logger.info("✓ Dropped index: billing_frequency_idx")
            except:
                pass

            try:
                self.db.invoices.drop_index("stripe_invoice_id_unique")
                logger.info("✓ Dropped index: stripe_invoice_id_unique")
            except:
                pass

            try:
                self.db.invoices.drop_index("amount_paid_idx")
                logger.info("✓ Dropped index: amount_paid_idx")
            except:
                pass

            try:
                self.db.payments.drop_index("invoice_id_idx")
                logger.info("✓ Dropped index: invoice_id_idx")
            except:
                pass

            try:
                self.db.payments.drop_index("subscription_id_idx")
                logger.info("✓ Dropped index: subscription_id_idx")
            except:
                pass

            logger.info("✓ Rollback completed")
            return True

        except Exception as e:
            logger.error(f"✗ Rollback failed: {e}", exc_info=True)
            return False

    def print_summary(self, success: bool):
        """Print migration summary."""
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("Mode: DRY RUN (no changes made)")
        elif success:
            logger.info("Status: SUCCESS ✓")
        else:
            logger.info("Status: FAILED ✗")

        logger.info("")
        logger.info(f"Started at: {self.migration_log['started_at']}")
        logger.info(f"Completed at: {datetime.now(timezone.utc)}")
        logger.info(f"Database: {self.database_name}")
        logger.info("")

        if self.migration_log["steps_completed"]:
            logger.info("Steps completed:")
            for step in self.migration_log["steps_completed"]:
                logger.info(f"  ✓ {step}")

        if self.migration_log["steps_failed"]:
            logger.info("")
            logger.info("Steps failed:")
            for step, error in self.migration_log["steps_failed"]:
                logger.info(f"  ✗ {step}: {error}")

        logger.info("")
        logger.info("=" * 80)

    def run(self) -> bool:
        """
        Execute the migration.

        Returns:
            bool: True if migration successful, False otherwise
        """
        try:
            # Check preconditions
            if not self.check_preconditions():
                logger.error("Preconditions not met. Aborting migration.")
                return False

            # Execute migration steps
            if not self.step1_migrate_subscriptions():
                logger.error("Step 1 failed. Aborting migration.")
                return False

            if not self.step2_migrate_invoices():
                logger.error("Step 2 failed. Aborting migration.")
                return False

            if not self.step3_migrate_payments():
                logger.error("Step 3 failed. Aborting migration.")
                return False

            if not self.step4_create_indexes():
                logger.error("Step 4 failed. Aborting migration.")
                return False

            # Verify migration (skip in dry-run mode)
            if not self.dry_run:
                if not self.verify_migration():
                    logger.error("Migration verification failed!")
                    return False

            return True

        except Exception as e:
            logger.error(f"Migration failed with unexpected error: {e}", exc_info=True)
            return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Billing Schema Enhancement Migration")
    parser.add_argument(
        "--database",
        default="translation_test",
        choices=["translation", "translation_test"],
        help="Database to migrate (default: translation_test)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (remove new fields)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration without running it"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for production database migration"
    )

    args = parser.parse_args()

    # Safety check for production database
    if args.database == "translation" and not args.confirm and not args.dry_run:
        logger.error("ERROR: Production database migration requires --confirm flag")
        logger.error("Use --dry-run to preview changes first")
        sys.exit(1)

    migration = BillingSchemaEnhancementMigration(
        database_name=args.database,
        dry_run=args.dry_run
    )

    try:
        # Connect to MongoDB
        if not migration.connect():
            logger.error("Failed to connect to MongoDB. Exiting.")
            sys.exit(1)

        # Handle rollback
        if args.rollback:
            if args.database == "translation" and not args.confirm:
                logger.error("ERROR: Production rollback requires --confirm flag")
                sys.exit(1)

            success = migration.rollback()
            migration.print_summary(success)
            sys.exit(0 if success else 1)

        # Handle verify-only
        if args.verify:
            success = migration.verify_migration()
            sys.exit(0 if success else 1)

        # Run migration
        success = migration.run()

        # Print summary
        migration.print_summary(success)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Always disconnect
        migration.disconnect()


if __name__ == "__main__":
    main()
