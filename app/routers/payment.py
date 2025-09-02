"""
Payment API endpoints for Stripe integration.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.models.requests import PaymentIntentRequest, PaymentHistoryRequest
from app.models.responses import (
    PaymentIntentResponse,
    PricingResponse,
    PaymentHistoryResponse,
    BaseResponse,
    WebhookResponse
)
from app.services.payment_service import payment_service

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.get(
    "/pricing",
    response_model=PricingResponse,
    summary="Get pricing information",
    description="Get current pricing tiers and rates"
)
async def get_pricing():
    """
    Get pricing information for translation services - WITH STUB IMPLEMENTATION.
    
    Returns available pricing tiers with rates and features.
    """
    print("Hello World - Get pricing endpoint called")
    try:
        pricing_tiers = payment_service.get_pricing_tiers()
        
        return PricingResponse(
            tiers=[
                {
                    'name': tier['name'],
                    'price_per_character': tier['price_per_char'],
                    'min_characters': tier['min_chars'],
                    'max_characters': tier['max_chars'],
                    'features': tier['features']
                }
                for tier in pricing_tiers
            ],
            currency="USD",
            message="Pricing information retrieved successfully"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pricing: {str(e)}"
        )


@router.post(
    "/calculate",
    summary="Calculate translation cost",
    description="Calculate cost for translation based on character count"
)
async def calculate_translation_cost(
    characters: int = Query(..., ge=1, description="Number of characters"),
    tier: str = Query("basic", description="Pricing tier (basic, professional, enterprise)")
):
    """
    Calculate translation cost based on character count and pricing tier.
    
    - **characters**: Number of characters to translate
    - **tier**: Pricing tier (basic, professional, enterprise)
    
    Returns detailed cost calculation with pricing breakdown.
    """
    try:
        calculation = payment_service.calculate_price(characters, tier)
        
        return JSONResponse(
            content={
                'success': True,
                'cost_calculation': calculation,
                'message': "Cost calculation completed successfully"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cost calculation failed: {str(e)}"
        )


@router.post(
    "/intent",
    response_model=PaymentIntentResponse,
    summary="Create payment intent",
    description="Create a Stripe payment intent for translation payment"
)
async def create_payment_intent(request: PaymentIntentRequest):
    """
    Create a payment intent for translation services - WITH STUB IMPLEMENTATION.
    
    - **amount**: Payment amount in dollars
    - **currency**: Payment currency (default USD)
    - **description**: Payment description
    - **metadata**: Additional metadata for the payment
    
    Returns payment intent with client secret for frontend processing.
    """
    print(f"Hello World - Create payment intent endpoint called: ${request.amount} {request.currency}")
    try:
        payment_intent = await payment_service.create_payment_intent(
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            metadata=request.metadata
        )
        
        return PaymentIntentResponse(
            payment_intent=payment_intent,
            message="Payment intent created successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment intent: {str(e)}"
        )


@router.post(
    "/intent/{payment_intent_id}/confirm",
    summary="Confirm payment intent",
    description="Confirm a payment intent"
)
async def confirm_payment_intent(payment_intent_id: str):
    """
    Confirm a payment intent.
    
    - **payment_intent_id**: Stripe payment intent ID
    
    Returns payment confirmation details.
    """
    try:
        confirmation = await payment_service.confirm_payment(payment_intent_id)
        
        return JSONResponse(
            content={
                'success': True,
                'payment_confirmation': confirmation,
                'message': "Payment confirmed successfully"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Payment confirmation failed: {str(e)}"
        )


@router.get(
    "/intent/{payment_intent_id}",
    summary="Get payment status",
    description="Get current status of a payment intent"
)
async def get_payment_status(payment_intent_id: str):
    """
    Get payment intent status.
    
    - **payment_intent_id**: Stripe payment intent ID
    
    Returns current payment status and details.
    """
    try:
        payment_info = await payment_service.get_payment_status(payment_intent_id)
        
        return JSONResponse(
            content={
                'success': True,
                'payment_info': payment_info,
                'message': "Payment status retrieved successfully"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get payment status: {str(e)}"
        )


@router.post(
    "/intent/{payment_intent_id}/refund",
    summary="Refund payment",
    description="Process a refund for a completed payment"
)
async def refund_payment(
    payment_intent_id: str,
    amount: Optional[float] = Query(None, description="Refund amount (full refund if not specified)"),
    reason: Optional[str] = Query(None, description="Refund reason")
):
    """
    Process a refund for a payment.
    
    - **payment_intent_id**: Stripe payment intent ID
    - **amount**: Partial refund amount (full refund if not specified)
    - **reason**: Reason for the refund
    
    Returns refund confirmation details.
    """
    try:
        refund_info = await payment_service.refund_payment(
            payment_intent_id=payment_intent_id,
            amount=amount,
            reason=reason
        )
        
        return JSONResponse(
            content={
                'success': True,
                'refund_info': refund_info,
                'message': "Refund processed successfully"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Refund processing failed: {str(e)}"
        )


@router.get(
    "/history",
    response_model=PaymentHistoryResponse,
    summary="Get payment history",
    description="Get paginated payment history"
)
async def get_payment_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID")
):
    """
    Get payment history with pagination and filtering.
    
    - **page**: Page number (starting from 1)
    - **page_size**: Items per page (1-100)
    - **status**: Filter by payment status
    - **customer_id**: Filter by Stripe customer ID
    
    Returns paginated payment history.
    """
    try:
        # Calculate starting_after for pagination
        starting_after = None
        if page > 1:
            # In a real implementation, you'd store the last item ID from previous page
            pass
        
        payments = await payment_service.get_payment_history(
            customer_id=customer_id,
            limit=page_size,
            starting_after=starting_after
        )
        
        return PaymentHistoryResponse(
            payments=payments,
            total_count=len(payments),  # In real implementation, get actual count
            page=page,
            page_size=page_size,
            message=f"Retrieved {len(payments)} payment records"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve payment history: {str(e)}"
        )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    summary="Handle Stripe webhooks",
    description="Endpoint for receiving Stripe webhook events"
)
async def handle_stripe_webhook(request: Request):
    """
    Handle Stripe webhook events - WITH STUB IMPLEMENTATION.
    
    This endpoint receives webhook events from Stripe for payment status updates.
    """
    print("Hello World - Stripe webhook endpoint called")
    try:
        # Get the request body and Stripe signature
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(
                status_code=400,
                detail="Missing Stripe signature header"
            )
        
        # Process the webhook
        result = await payment_service.handle_webhook(
            payload=payload.decode('utf-8'),
            signature=signature
        )
        
        return WebhookResponse(
            event_id=result.get('event_id', 'unknown'),
            processed=True,
            message="Webhook processed successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.get(
    "/methods",
    summary="Get payment methods",
    description="Get available payment methods and their information"
)
async def get_payment_methods():
    """
    Get available payment methods.
    
    Returns information about supported payment methods.
    """
    try:
        methods = [
            {
                'type': 'card',
                'name': 'Credit/Debit Card',
                'description': 'Visa, Mastercard, American Express, and other major cards',
                'supported_currencies': ['USD', 'EUR', 'GBP'],
                'processing_time': 'Instant',
                'fees': 'Standard processing fees apply'
            },
            {
                'type': 'bank_transfer',
                'name': 'Bank Transfer',
                'description': 'Direct bank account transfer',
                'supported_currencies': ['USD', 'EUR'],
                'processing_time': '1-3 business days',
                'fees': 'Lower fees for larger amounts'
            }
        ]
        
        return JSONResponse(
            content={
                'success': True,
                'payment_methods': methods,
                'default_currency': 'USD',
                'minimum_amount': payment_service.minimum_charge,
                'message': "Payment methods retrieved successfully"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve payment methods: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get payment statistics",
    description="Get payment and revenue statistics"
)
async def get_payment_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics")
):
    """
    Get payment statistics.
    
    - **days**: Number of days to include in statistics (1-365)
    
    Returns payment volume, revenue, and trend data.
    """
    try:
        # This would typically query a database for actual statistics
        # For now, return placeholder data
        stats = {
            'period_days': days,
            'total_payments': 0,
            'total_revenue': 0.0,
            'successful_payments': 0,
            'failed_payments': 0,
            'refunded_amount': 0.0,
            'average_payment_amount': 0.0,
            'payment_methods': {
                'card': 0,
                'bank_transfer': 0
            },
            'daily_revenue': [],
            'top_amounts': []
        }
        
        return JSONResponse(
            content={
                'success': True,
                'statistics': stats,
                'message': f"Payment statistics for last {days} days retrieved"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get payment statistics: {str(e)}"
        )


@router.get(
    "/config",
    summary="Get payment configuration",
    description="Get payment service configuration and limits"
)
async def get_payment_config():
    """
    Get payment service configuration.
    
    Returns configuration information like limits, currencies, and service status.
    """
    try:
        config = {
            'service_enabled': payment_service.stripe_enabled,
            'minimum_amount': payment_service.minimum_charge,
            'supported_currencies': ['USD', 'EUR', 'GBP', 'JPY'],
            'default_currency': 'USD',
            'pricing_tiers': list(payment_service.pricing_tiers.keys()),
            'webhook_configured': bool(payment_service.stripe_enabled),
            'features': {
                'refunds': True,
                'partial_refunds': True,
                'webhooks': True,
                'payment_history': True,
                'multiple_currencies': True
            }
        }
        
        return JSONResponse(
            content={
                'success': True,
                'configuration': config,
                'message': "Payment configuration retrieved successfully"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get payment configuration: {str(e)}"
        )