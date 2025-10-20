#!/usr/bin/env python3
"""Test 6 core MongoDB collections."""

import pytest
from pymongo import MongoClient
from pymongo.errors import WriteError
from bson import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime, timezone

MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"

@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGODB_URI)
    yield client.translation
    client.close()

def test_company_exists(db):
    assert "company" in db.list_collection_names()

def test_company_valid_insert(db):
    doc = {"company_name": "Test Corp", "created_at": datetime.now(timezone.utc)}
    result = db.company.insert_one(doc)
    assert result.inserted_id
    db.company.delete_one({"_id": result.inserted_id})

def test_company_invalid_insert(db):
    with pytest.raises(WriteError):
        db.company.insert_one({"address": "123 Main St"})

def test_company_users_exists(db):
    assert "company_users" in db.list_collection_names()

def test_company_users_valid_insert(db):
    doc = {
        "user_id": f"test_{ObjectId()}",
        "customer_id": ObjectId(),
        "user_name": "Test User",
        "email": "test@example.com",
        "created_at": datetime.now(timezone.utc)
    }
    result = db.company_users.insert_one(doc)
    assert result.inserted_id
    db.company_users.delete_one({"_id": result.inserted_id})

def test_company_users_invalid_insert(db):
    with pytest.raises(WriteError):
        db.company_users.insert_one({"user_name": "No ID"})

def test_subscriptions_exists(db):
    assert "subscriptions" in db.list_collection_names()

def test_subscriptions_valid_insert(db):
    doc = {
        "customer_id": ObjectId(),
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": Decimal128("0.10"),
        "subscription_price": Decimal128("100.00"),
        "start_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc)
    }
    result = db.subscriptions.insert_one(doc)
    assert result.inserted_id
    db.subscriptions.delete_one({"_id": result.inserted_id})

def test_invoices_exists(db):
    assert "invoices" in db.list_collection_names()

def test_invoices_valid_insert(db):
    doc = {
        "customer_id": ObjectId(),
        "invoice_number": f"INV-{ObjectId()}",
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc),
        "total_amount": Decimal128("100.00"),
        "created_at": datetime.now(timezone.utc)
    }
    result = db.invoices.insert_one(doc)
    assert result.inserted_id
    db.invoices.delete_one({"_id": result.inserted_id})

def test_payments_exists(db):
    assert "payments" in db.list_collection_names()

def test_payments_valid_insert(db):
    doc = {
        "customer_id": ObjectId(),
        "square_payment_id": f"sq_{ObjectId()}",
        "amount": Decimal128("106.00"),
        "payment_status": "completed",
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc)
    }
    result = db.payments.insert_one(doc)
    assert result.inserted_id
    db.payments.delete_one({"_id": result.inserted_id})

def test_translation_transactions_exists(db):
    assert "translation_transactions" in db.list_collection_names()

def test_translation_transactions_valid_insert(db):
    doc = {
        "customer_id": ObjectId(),
        "requester_id": "user123",
        "user_name": "Test User",
        "transaction_date": datetime.now(timezone.utc),
        "units_consumed": 10,
        "original_file_url": "https://example.com/file.pdf",
        "source_language": "en",
        "target_language": "es",
        "created_at": datetime.now(timezone.utc)
    }
    result = db.translation_transactions.insert_one(doc)
    assert result.inserted_id
    db.translation_transactions.delete_one({"_id": result.inserted_id})
