"""
Payment service for Stripe integration.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
import uuid

from app.config import settings
from app.models.responses import PaymentIntent, PaymentStatus, PaymentHistory


class PaymentService:
    """Service for handling payments through Stripe."""
    
    def __init__(self):
        print("Hello World - Payment service initialization stub")
        # Stub - always consider payment service "enabled" for demo
        self.stripe_enabled = True
        
        # Pricing tiers (in USD per character)
        self.pricing_tiers = {
            'basic': {
                'name': 'Basic',
                'price_per_char': 0.00001,  # $0.01 per 1000 characters
                'min_chars': 1,
                'max_chars': 50000,
                'features': ['Standard translation', 'Basic support']
            },
            'professional': {
                'name': 'Professional',
                'price_per_char': 0.00002,  # $0.02 per 1000 characters
                'min_chars': 1,
                'max_chars': 500000,
                'features': ['Premium translation', 'Priority support', 'Custom formatting']
            },
            'enterprise': {
                'name': 'Enterprise',
                'price_per_char': 0.00003,  # $0.03 per 1000 characters
                'min_chars': 1,
                'max_chars': None,
                'features': ['Enterprise translation', '24/7 support', 'Custom integrations', 'SLA guarantee']
            }
        }
        
        # Minimum charge amount (to avoid micro-transactions)
        self.minimum_charge = 0.50  # $0.50
    
    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "USD",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> PaymentIntent:
        """
        Create a Stripe payment intent - STUB IMPLEMENTATION.
        
        Args:
            amount: Payment amount in dollars
            currency: Payment currency (default USD)
            description: Payment description
            metadata: Additional metadata
            
        Returns:
            PaymentIntent object
            
        Raises:
            HTTPException: If Stripe is not configured or payment creation fails
        """
        print(f"Hello World - Payment intent creation stub: ${amount} {currency}")
        print(f"Description: {description}")
        print(f"Metadata: {metadata}")
        
        if amount < self.minimum_charge:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum payment amount is ${self.minimum_charge}"
            )
        
        # Create stub payment intent
        stub_intent_id = f"pi_stub_{uuid.uuid4().hex[:16]}"
        stub_client_secret = f"pi_stub_{uuid.uuid4().hex[:16]}_secret_{uuid.uuid4().hex[:8]}"
        
        return PaymentIntent(
            payment_intent_id=stub_intent_id,
            client_secret=stub_client_secret,
            amount=amount,
            currency=currency,
            status=PaymentStatus.PENDING
        )
    
    async def confirm_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a payment intent - STUB IMPLEMENTATION.
        
        Args:
            payment_intent_id: Stripe payment intent ID
            
        Returns:
            Payment confirmation details
        """
        print(f"Hello World - Payment confirmation stub for: {payment_intent_id}")
        
        return {
            'payment_intent_id': payment_intent_id,
            'status': 'succeeded',
            'amount': 10.00,  # Stub amount
            'currency': 'USD'
        }
    
    async def get_payment_status(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Get payment status - STUB IMPLEMENTATION.
        
        Args:
            payment_intent_id: Stripe payment intent ID
            
        Returns:
            Payment status information
        """
        print(f"Hello World - Payment status check stub for: {payment_intent_id}")
        
        return {
            'payment_intent_id': payment_intent_id,
            'status': PaymentStatus.SUCCEEDED,
            'amount': 10.00,  # Stub amount
            'currency': 'USD',
            'created': datetime.now(timezone.utc),
            'metadata': {'stub': 'true'}
        }
    
    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment - STUB IMPLEMENTATION.
        
        Args:
            payment_intent_id: Stripe payment intent ID
            amount: Refund amount (full refund if None)
            reason: Refund reason
            
        Returns:
            Refund information
        """
        print(f"Hello World - Payment refund stub for: {payment_intent_id}")
        print(f"Amount: {amount}, Reason: {reason}")
        
        stub_refund_id = f"re_stub_{uuid.uuid4().hex[:16]}"
        refund_amount = amount or 10.00  # Default stub amount
        
        return {
            'refund_id': stub_refund_id,
            'payment_intent_id': payment_intent_id,
            'amount': refund_amount,
            'currency': 'USD',
            'status': 'succeeded',
            'reason': reason or 'requested_by_customer',
            'created': datetime.now(timezone.utc)
        }
    
    def calculate_price(
        self,
        character_count: int,
        tier: str = 'basic'
    ) -> Dict[str, Any]:
        """
        Calculate price for translation based on character count and tier.
        
        Args:
            character_count: Number of characters to translate
            tier: Pricing tier
            
        Returns:
            Price calculation details
        """
        if tier not in self.pricing_tiers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pricing tier: {tier}"
            )
        
        tier_info = self.pricing_tiers[tier]
        
        # Check character limits
        if character_count < tier_info['min_chars']:
            raise HTTPException(
                status_code=400,
                detail=f"Character count below minimum for {tier} tier"
            )
        
        if tier_info['max_chars'] and character_count > tier_info['max_chars']:
            raise HTTPException(
                status_code=400,
                detail=f"Character count exceeds maximum for {tier} tier"
            )
        
        # Calculate base price
        base_price = character_count * tier_info['price_per_char']
        
        # Apply minimum charge
        final_price = max(base_price, self.minimum_charge)
        
        return {
            'character_count': character_count,
            'tier': tier,
            'tier_name': tier_info['name'],
            'price_per_char': tier_info['price_per_char'],
            'base_price': round(base_price, 2),
            'minimum_charge': self.minimum_charge,
            'final_price': round(final_price, 2),
            'currency': 'USD',
            'features': tier_info['features']
        }
    
    def get_pricing_tiers(self) -> List[Dict[str, Any]]:
        """
        Get all available pricing tiers.
        
        Returns:
            List of pricing tier information
        """
        return [
            {
                'id': tier_id,
                'name': tier_info['name'],
                'price_per_char': tier_info['price_per_char'],
                'price_per_1000_chars': tier_info['price_per_char'] * 1000,
                'min_chars': tier_info['min_chars'],
                'max_chars': tier_info['max_chars'],
                'features': tier_info['features']
            }
            for tier_id, tier_info in self.pricing_tiers.items()
        ]
    
    async def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events - STUB IMPLEMENTATION.
        
        Args:
            payload: Webhook payload
            signature: Stripe signature header
            
        Returns:
            Webhook processing result
        """
        print(f"Hello World - Webhook handling stub")
        print(f"Payload length: {len(payload)}, Signature: {signature[:20]}...")
        
        # Return stub webhook response
        return {
            'status': 'processed',
            'event_type': 'payment_intent.succeeded',
            'message': 'Webhook processed successfully (stub)',
            'processed_at': datetime.now(timezone.utc)
        }
    
    async def get_payment_history(
        self,
        customer_id: Optional[str] = None,
        limit: int = 20,
        starting_after: Optional[str] = None
    ) -> List[PaymentHistory]:
        """
        Get payment history - STUB IMPLEMENTATION.
        
        Args:
            customer_id: Stripe customer ID (optional)
            limit: Number of payments to retrieve
            starting_after: Pagination cursor
            
        Returns:
            List of payment history records
        """
        print(f"Hello World - Payment history stub - customer: {customer_id}, limit: {limit}")
        
        # Return stub payment history
        stub_history = [
            PaymentHistory(
                payment_id=f"ch_stub_1_{uuid.uuid4().hex[:8]}",
                amount=10.50,
                currency="USD",
                status=PaymentStatus.SUCCEEDED,
                description="Translation service payment (stub)",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ),
            PaymentHistory(
                payment_id=f"ch_stub_2_{uuid.uuid4().hex[:8]}",
                amount=25.00,
                currency="USD",
                status=PaymentStatus.SUCCEEDED,
                description="Premium translation service (stub)",
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
                updated_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
        ]
        
        return stub_history[:limit]
    
    # Private webhook handlers
    
    async def _handle_payment_succeeded(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook - STUB IMPLEMENTATION."""
        print(f"Hello World - Payment succeeded webhook stub for: {payment_intent.get('id', 'unknown')}")
        return {
            'status': 'processed',
            'event_type': 'payment_intent.succeeded',
            'payment_intent_id': payment_intent.get('id', 'stub_intent'),
            'amount': payment_intent.get('amount', 1000) / 100  # Default 10.00
        }
    
    async def _handle_payment_failed(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment webhook - STUB IMPLEMENTATION."""
        print(f"Hello World - Payment failed webhook stub for: {payment_intent.get('id', 'unknown')}")
        return {
            'status': 'processed',
            'event_type': 'payment_intent.payment_failed',
            'payment_intent_id': payment_intent.get('id', 'stub_intent'),
            'amount': payment_intent.get('amount', 1000) / 100  # Default 10.00
        }
    
    async def _handle_dispute_created(self, charge: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dispute creation webhook - STUB IMPLEMENTATION."""
        print(f"Hello World - Dispute created webhook stub for: {charge.get('id', 'unknown')}")
        return {
            'status': 'processed',
            'event_type': 'charge.dispute.created',
            'charge_id': charge.get('id', 'stub_charge'),
            'amount': charge.get('amount', 1000) / 100  # Default 10.00
        }


# Global payment service instance
payment_service = PaymentService()