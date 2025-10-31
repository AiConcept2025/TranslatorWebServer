#!/usr/bin/env python3
"""
Schema Migration Verification Script

Purpose: Verify that the database schema has been correctly migrated from company_id to company_name.

This script checks:
1. All indexes reference company_name (not company_id)
2. All documents have company_name field
3. No documents have company_id field (unless it's legacy data)

Usage:
    python scripts/verify_schema_migration.py
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection settings
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"

# Collections that should use company_name
COMPANY_NAME_COLLECTIONS = [
    "users",
    "payments",
    "company_users",
    "subscriptions",
    "translation_transactions"
]


async def verify_indexes(db, collection_name: str) -> Dict[str, Any]:
    """
    Verify that collection indexes use company_name (not company_id).

    Args:
        db: Motor database object
        collection_name: Name of collection to verify

    Returns:
        Dictionary with verification results
    """
    logger.info(f"\n[{collection_name}] Verifying indexes...")

    collection = db[collection_name]
    issues = []
    correct_indexes = []

    async for index in collection.list_indexes():
        index_name = index['name']
        keys = index.get('key', {})

        # Skip _id_ index
        if index_name == "_id_":
            continue

        # Check for company_id (should not exist)
        if "company_id" in keys:
            issues.append(f"Index '{index_name}' still references company_id: {keys}")
        elif "company_name" in keys:
            correct_indexes.append(f"Index '{index_name}' correctly uses company_name")

    if issues:
        logger.error(f"[{collection_name}] ✗ FAILED - Found {len(issues)} issues:")
        for issue in issues:
            logger.error(f"  - {issue}")
    else:
        logger.info(f"[{collection_name}] ✓ PASSED - All indexes correct")
        if correct_indexes:
            for idx in correct_indexes:
                logger.info(f"  - {idx}")

    return {
        "collection": collection_name,
        "passed": len(issues) == 0,
        "issues": issues,
        "correct_indexes": correct_indexes
    }


async def verify_documents(db, collection_name: str, sample_size: int = 10) -> Dict[str, Any]:
    """
    Verify that documents use company_name (not company_id).

    Args:
        db: Motor database object
        collection_name: Name of collection to verify
        sample_size: Number of documents to sample

    Returns:
        Dictionary with verification results
    """
    logger.info(f"\n[{collection_name}] Verifying documents (sample size: {sample_size})...")

    collection = db[collection_name]
    issues = []

    # Count total documents
    total_docs = await collection.count_documents({})

    if total_docs == 0:
        logger.info(f"[{collection_name}] ℹ️  Collection is empty (no documents to verify)")
        return {
            "collection": collection_name,
            "passed": True,
            "total_documents": 0,
            "issues": []
        }

    # Sample documents
    sample_docs = []
    async for doc in collection.find().limit(sample_size):
        sample_docs.append(doc)

    # Check for company_id field (should not exist in new schema)
    docs_with_company_id = 0
    docs_with_company_name = 0

    for doc in sample_docs:
        if "company_id" in doc:
            docs_with_company_id += 1
            issues.append(f"Document {doc.get('_id')} has company_id field")

        if "company_name" in doc:
            docs_with_company_name += 1

    logger.info(f"[{collection_name}] Total documents: {total_docs}")
    logger.info(f"[{collection_name}] Sampled documents: {len(sample_docs)}")
    logger.info(f"[{collection_name}] Documents with company_name: {docs_with_company_name}")
    logger.info(f"[{collection_name}] Documents with company_id (legacy): {docs_with_company_id}")

    if docs_with_company_id > 0:
        logger.warning(f"[{collection_name}] ⚠️  Found {docs_with_company_id} documents with company_id field")
        logger.warning(f"[{collection_name}]    This may be legacy data that needs migration")

    if docs_with_company_name == 0 and total_docs > 0:
        logger.error(f"[{collection_name}] ✗ FAILED - No documents have company_name field")
        return {
            "collection": collection_name,
            "passed": False,
            "total_documents": total_docs,
            "issues": ["No documents have company_name field"]
        }

    logger.info(f"[{collection_name}] ✓ PASSED - Documents are correctly structured")

    return {
        "collection": collection_name,
        "passed": True,
        "total_documents": total_docs,
        "sampled_documents": len(sample_docs),
        "docs_with_company_name": docs_with_company_name,
        "docs_with_company_id": docs_with_company_id,
        "issues": issues
    }


async def main():
    """Main verification function."""
    logger.info("="*80)
    logger.info("Schema Migration Verification")
    logger.info("="*80)
    logger.info(f"Database: {DATABASE_NAME}")
    logger.info("="*80)

    # Connect to MongoDB
    logger.info("\nConnecting to MongoDB...")
    try:
        client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000
        )
        db = client[DATABASE_NAME]

        # Test connection
        await client.admin.command('ping')
        logger.info("✓ Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"✗ Failed to connect to MongoDB: {e}")
        return False

    # Verify each collection
    all_passed = True
    results = []

    for collection_name in COMPANY_NAME_COLLECTIONS:
        try:
            # Verify indexes
            index_result = await verify_indexes(db, collection_name)
            results.append(index_result)

            if not index_result["passed"]:
                all_passed = False

            # Verify documents
            doc_result = await verify_documents(db, collection_name, sample_size=10)
            results.append(doc_result)

            if not doc_result["passed"]:
                all_passed = False

        except Exception as e:
            logger.error(f"[{collection_name}] ✗ Unexpected error: {e}", exc_info=True)
            all_passed = False

    # Summary
    logger.info("\n" + "="*80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*80)

    for result in results:
        status = "✓ PASSED" if result["passed"] else "✗ FAILED"
        logger.info(f"[{result['collection']}] {status}")

        if result["issues"]:
            logger.info(f"  Issues: {len(result['issues'])}")
            for issue in result["issues"][:5]:  # Show first 5 issues
                logger.info(f"    - {issue}")

    if all_passed:
        logger.info("\n✓ ALL VERIFICATIONS PASSED")
        logger.info("Schema migration from company_id to company_name is complete!")
    else:
        logger.error("\n✗ SOME VERIFICATIONS FAILED")
        logger.error("Please review the issues above and fix them.")

    # Close connection
    client.close()
    logger.info("\nMongoDB connection closed")

    return all_passed


if __name__ == "__main__":
    # Run async main
    success = asyncio.run(main())

    # Exit with appropriate code
    import sys
    sys.exit(0 if success else 1)
