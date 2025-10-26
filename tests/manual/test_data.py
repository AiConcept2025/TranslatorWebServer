"""
Test Data Generator for MongoDB Collections
Creates realistic test data with proper referential integrity.
"""

from datetime import datetime, timezone, timedelta
from bson import ObjectId
from bson.decimal128 import Decimal128


class TestDataGenerator:
    """Generate test data for all collections."""

    def __init__(self):
        """Initialize with references that will be set during data generation."""
        self.company_id = None
        self.user_id = None
        self.subscription_id = None
        self.invoice_id = None
        self.payment_id = None

    def generate_all(self):
        """Generate all test data with proper relationships (6 collections only)."""
        # Generate in order of dependencies
        company_data = self.generate_company()
        user_data = self.generate_company_user(self.company_id)
        subscription_data = self.generate_subscription(self.company_id)
        invoice_data = self.generate_invoice(self.company_id, self.subscription_id)
        payment_data = self.generate_payment(self.company_id, self.subscription_id)
        transaction_data = self.generate_translation_transaction(
            self.company_id,
            self.subscription_id,
            user_data['user_id']
        )

        return {
            'company': company_data,
            'company_users': user_data,
            'subscriptions': subscription_data,
            'invoices': invoice_data,
            'payments': payment_data,
            'translation_transactions': transaction_data
        }

    def generate_company(self):
        """Generate test company data."""
        self.company_id = ObjectId()
        return {
            "_id": self.company_id,
            "company_id": f"COMP-{str(self.company_id)[:8].upper()}",
            "description": "A test company for translation services",
            "company_name": "Acme Translation Corp",
            "address": {
                "address0": "123 Main Street",
                "address1": "Suite 100",
                "postal_code": "10001",
                "state": "NY",
                "city": "New York",
                "country": "USA"
            },
            "contact_person": {
                "name": "John Doe",
                "type": "Primary Contact"
            },
            "phone_number": ["+1-555-0100", "+1-555-0101"],
            "company_url": ["https://acmetranslation.example.com"],
            "line_of_business": "Professional Translation Services",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

    def generate_company_user(self, company_id):
        """Generate test company user data."""
        user_id = f"user_{str(ObjectId())[:12]}"
        self.user_id = user_id
        return {
            "user_id": user_id,
            "company_id": company_id,
            "user_name": "Jane Smith",
            "email": "jane.smith@acmetranslation.example.com",
            "phone_number": "+1-555-0101",
            "permission_level": "admin",
            "status": "active",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyD1RnOqtZW2",  # hashed "password123"
            "last_login": datetime.now(timezone.utc) - timedelta(hours=2),
            "created_at": datetime.now(timezone.utc) - timedelta(days=30),
            "updated_at": datetime.now(timezone.utc)
        }

    def generate_subscription(self, company_id):
        """Generate test subscription data."""
        self.subscription_id = ObjectId()
        return {
            "_id": self.subscription_id,
            "company_id": company_id,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": Decimal128("0.10"),
            "promotional_units": 100,
            "discount": Decimal128("1.0"),
            "subscription_price": Decimal128("100.00"),
            "start_date": datetime.now(timezone.utc) - timedelta(days=15),
            "end_date": datetime.now(timezone.utc) + timedelta(days=345),  # 1 year subscription
            "status": "active",
            "created_at": datetime.now(timezone.utc) - timedelta(days=15),
            "updated_at": datetime.now(timezone.utc)
        }

    def generate_invoice(self, company_id, subscription_id):
        """Generate test invoice data."""
        self.invoice_id = ObjectId()
        return {
            "_id": self.invoice_id,
            "company_id": company_id,
            "subscription_id": subscription_id,
            "invoice_number": f"INV-{datetime.now().year}-{str(self.invoice_id)[:8].upper()}",
            "invoice_date": datetime.now(timezone.utc) - timedelta(days=5),
            "due_date": datetime.now(timezone.utc) + timedelta(days=25),  # 30 days net
            "total_amount": Decimal128("106.00"),  # $100 + 6% tax
            "tax_amount": Decimal128("6.00"),
            "status": "sent",
            "pdf_url": "https://storage.example.com/invoices/inv-123456.pdf",
            "created_at": datetime.now(timezone.utc) - timedelta(days=5)
        }

    def generate_payment(self, company_id, subscription_id):
        """Generate test payment data."""
        self.payment_id = ObjectId()
        return {
            "_id": self.payment_id,
            "company_id": company_id,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_{str(self.payment_id)[:16]}",
            "square_order_id": f"sq_order_{str(ObjectId())[:16]}",
            "square_receipt_url": "https://square.example.com/receipts/12345",
            "amount": Decimal128("106.00"),
            "currency": "USD",
            "payment_status": "completed",
            "payment_method": "card",
            "card_brand": "VISA",
            "last_4_digits": "4242",
            "processing_fee": Decimal128("3.38"),  # ~3.2% processing fee
            "net_amount": Decimal128("102.62"),
            "refunded_amount": Decimal128("0.00"),
            "payment_date": datetime.now(timezone.utc) - timedelta(days=3),
            "notes": "Payment for annual subscription",
            "created_at": datetime.now(timezone.utc) - timedelta(days=3),
            "updated_at": datetime.now(timezone.utc) - timedelta(days=3)
        }

    def generate_translation_transaction(self, company_id, subscription_id, requester_id):
        """Generate test translation transaction data."""
        return {
            "company_id": company_id,
            "subscription_id": subscription_id,
            "requester_id": requester_id,
            "user_name": "Jane Smith",
            "transaction_date": datetime.now(timezone.utc) - timedelta(hours=1),
            "units_consumed": 15,
            "original_file_url": "https://storage.example.com/uploads/document_en.pdf",
            "translated_file_url": "https://storage.example.com/translations/document_es.pdf",
            "source_language": "en",
            "target_language": "es",
            "status": "completed",
            "error_message": None,
            "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "updated_at": datetime.now(timezone.utc) - timedelta(minutes=50)
        }


def generate_test_data():
    """Generate and return all test data."""
    generator = TestDataGenerator()
    return generator.generate_all()


if __name__ == "__main__":
    # Test the data generator
    import json
    from bson import json_util

    data = generate_test_data()
    print("Generated test data:")
    for collection, doc in data.items():
        print(f"\n{collection}:")
        print(json.dumps(doc, indent=2, default=json_util.default))
